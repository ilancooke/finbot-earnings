"""Single-table, strongly consistent reference adapter with transactional fencing."""

from dataclasses import asdict
from datetime import timedelta
import uuid

from boto3.dynamodb.conditions import Attr, ConditionExpressionBuilder

from .contracts import json_text, json_value, utc_text
from .errors import StaleClaim, TechnicalFailure, WorkBusy, WorkConflict
from .reconciliation import plan_completion


class DynamoDBProcessingRepository:
    """Use a DynamoDB resource's auto-marshalling ``meta.client``.

    JOB partitions split immutable INPUT/RESPONSE from fenced STATE. EVENT
    partitions contain HEAD and preserved REV items with publication checkpoints.
    No scans, TTL-based locking, or unbounded aggregate records are required.
    """

    def __init__(self, client, table_name):
        self.client, self.table_name = client, table_name

    def _get(self, pk, sk):
        return self.client.get_item(TableName=self.table_name, Key=dict(pk=pk, sk=sk), ConsistentRead=True).get("Item")

    @staticmethod
    def _condition(expression):
        built = ConditionExpressionBuilder().build_expression(expression)
        result = {"ConditionExpression": built.condition_expression}
        if built.attribute_name_placeholders:
            result["ExpressionAttributeNames"] = built.attribute_name_placeholders
        if built.attribute_value_placeholders:
            result["ExpressionAttributeValues"] = built.attribute_value_placeholders
        return result

    def _put(self, item, condition):
        # JSON length overestimates native item bytes. Reserve room below 400 KiB
        # for attribute names and future metadata, even for Unicode or escaping.
        if len(json_text(item).encode()) > 380 * 1024:
            raise TechnicalFailure("dynamodb_item_exceeds_limit", retryable=False)
        return {"Put": dict(TableName=self.table_name, Item=item, **self._condition(condition))}

    def _transact(self, actions):
        if len(actions) > 100 or len(json_text(actions).encode()) > 3_800_000:
            raise TechnicalFailure("dynamodb_transaction_exceeds_limit", retryable=False)
        try:
            self.client.transact_write_items(TransactItems=actions, ClientRequestToken=uuid.uuid4().hex)
            return True
        except self.client.exceptions.TransactionCanceledException as exc:
            codes = [reason.get("Code") for reason in exc.response.get("CancellationReasons", [])]
            if codes and any(code in {"ConditionalCheckFailed", "TransactionConflict"} for code in codes) and all(
                    code in {None, "None", "ConditionalCheckFailed", "TransactionConflict"} for code in codes):
                return False
            raise

    def _read(self, work_id):
        pk = "JOB#" + work_id
        state = self._get(pk, "STATE")
        if state is None:
            return None, None
        job = json_value(state["record_json"])
        source = self._get(pk, "INPUT")
        if source is None:
            raise TechnicalFailure("missing_persisted_input", retryable=False)
        response = self._get(pk, "RESPONSE")
        job.update(input=json_value(source["record_json"]),
                   response=None if response is None else json_value(response["record_json"]))
        return job, int(state["version"])

    def get_job(self, work_id):
        return self._read(work_id)[0]

    def _state_put(self, job, version, *, token=None, now=None):
        condition = Attr("pk").not_exists() if version is None else Attr("version").eq(version)
        if token is not None:
            condition &= Attr("claim_token").eq(token) & Attr("lease_until").gt(utc_text(now))
        item = dict(pk="JOB#" + job["work_id"], sk="STATE", version=0 if version is None else version + 1,
            claim_token=job["claim_token"], lease_until=job["lease_until"],
            record_json=json_text({key: value for key, value in job.items() if key not in {"input", "response"}}))
        return self._put(item, condition)

    def _owned(self, work_id, token, now):
        job, version = self._read(work_id)
        if job is None or not token or job["claim_token"] != token or job["lease_until"] <= utc_text(now):
            raise StaleClaim("work claim expired or replaced")
        return job, version

    def claim(self, filing, config, identity, now):
        for _ in range(5):
            job, version = self._read(identity.work_id)
            actions = []
            if job is None:
                job = dict(work_id=identity.work_id, identity=asdict(identity), input=filing.to_dict(),
                    config=config.to_dict(), created_at=utc_text(now), attempt_count=0, claim_token=None,
                    lease_until=None, response=None, completion=None, failures={}, terminal=None)
                actions.append(self._put(dict(pk="JOB#" + identity.work_id, sk="INPUT",
                    record_json=json_text(job["input"])), Attr("pk").not_exists()))
            elif job["input"] != filing.to_dict() or job["config"] != config.to_dict() or job["identity"] != asdict(identity):
                raise WorkConflict("work identity reused with changed input/configuration")
            if job["terminal"] is not None or (job["completion"] is not None and not self.pending_publications(job["work_id"])):
                return job
            if job["claim_token"] is not None and job["lease_until"] > utc_text(now):
                raise WorkBusy("work already claimed")
            job.update(claim_token=uuid.uuid4().hex, lease_until=utc_text(now + timedelta(seconds=config.lease_seconds)),
                       attempt_count=job["attempt_count"] + 1)
            actions.append(self._state_put(job, version))
            if self._transact(actions):
                return job
        raise WorkBusy("claim contention")

    def save_response(self, work_id, token, response, now):
        for _ in range(5):
            job, version = self._owned(work_id, token, now)
            if job["response"] is not None:
                if job["response"] != response:
                    raise WorkConflict("saved model response is immutable")
                return job
            actions = [self._state_put(job, version, token=token, now=now), self._put(
                dict(pk="JOB#" + work_id, sk="RESPONSE", record_json=json_text(response)), Attr("pk").not_exists())]
            if self._transact(actions):
                job["response"] = response
                return job
        raise TechnicalFailure("checkpoint_contention")

    def complete(self, work_id, token, validation, now):
        for _ in range(5):
            job, version = self._owned(work_id, token, now)
            if job["completion"] is not None:
                return job
            completion, changes = plan_completion(job, validation, self.event, now)
            actions = []
            for event_id, prior_revision, payload in changes:
                condition = Attr("pk").not_exists() if prior_revision is None else Attr("revision").eq(prior_revision)
                pk = "EVENT#" + event_id
                if payload is None:
                    actions.append({"ConditionCheck": dict(TableName=self.table_name, Key=dict(pk=pk, sk="HEAD"),
                                                           **self._condition(condition))})
                else:
                    revision = payload["revision"]
                    actions.append(self._put(dict(pk=pk, sk="HEAD", revision=revision), condition))
                    actions.append(self._put(dict(pk=pk, sk=f"REV#{revision:010}", event_id=event_id,
                        revision=revision, payload_json=json_text(payload)), Attr("pk").not_exists()))
            job["completion"] = completion
            actions.append(self._state_put(job, version, token=token, now=now))
            if self._transact(actions):
                return job
        raise TechnicalFailure("revision_contention")

    def event(self, event_id, revision=None):
        pk = "EVENT#" + event_id
        if revision is None:
            head = self._get(pk, "HEAD")
            if head is None:
                return None
            revision = int(head["revision"])
        item = self._get(pk, f"REV#{revision:010}")
        return None if item is None else json_value(item["payload_json"])

    def pending_publications(self, work_id):
        job = self.get_job(work_id)
        if job is None or job["completion"] is None:
            return []
        pending = []
        for event_id, revision in job["completion"]["publications"]:
            item = self._get("EVENT#" + event_id, f"REV#{revision:010}")
            if item is None:
                raise TechnicalFailure("missing_persisted_publication", retryable=False)
            if "published_at" not in item:
                pending.append(dict(event_id=event_id, revision=revision, payload_json=item["payload_json"]))
        return pending

    def mark_published(self, work_id, token, event_id, revision, acknowledgment, now):
        if not isinstance(acknowledgment, str) or not acknowledgment.strip() or len(acknowledgment) > 200:
            raise TechnicalFailure("missing_publication_acknowledgment")
        for _ in range(5):
            job, version = self._owned(work_id, token, now)
            if job["completion"] is None or [event_id, revision] not in job["completion"]["publications"]:
                raise WorkConflict("publication does not belong to processing record")
            action = {"Update": dict(TableName=self.table_name,
                Key=dict(pk="EVENT#" + event_id, sk=f"REV#{revision:010}"),
                UpdateExpression="SET published_at=if_not_exists(published_at,:at), acknowledgment=if_not_exists(acknowledgment,:ack)",
                ConditionExpression="attribute_exists(pk)", ExpressionAttributeValues={":at": utc_text(now), ":ack": acknowledgment})}
            if self._transact([self._state_put(job, version, token=token, now=now), action]):
                return
        raise TechnicalFailure("publication_checkpoint_contention")

    def _mutate(self, work_id, token, now, change):
        for _ in range(5):
            job, version = self._owned(work_id, token, now)
            change(job)
            if self._transact([self._state_put(job, version, token=token, now=now)]):
                return job
        raise TechnicalFailure("checkpoint_contention")

    def release(self, work_id, token, now):
        self._mutate(work_id, token, now, lambda job: job.update(claim_token=None, lease_until=None))

    def fail(self, work_id, token, stage, code, retryable, now):
        def change(job):
            count = job["failures"].get(stage, 0) + 1
            job["failures"][stage] = count
            job["last_failure"] = dict(stage=stage, code=code, at=utc_text(now))
            if not retryable or count >= job["config"]["max_stage_failures"]:
                job["terminal"] = dict(job["last_failure"])
            job.update(claim_token=None, lease_until=None)
        return self._mutate(work_id, token, now, change)

    def rearm(self, work_id, now):
        for _ in range(5):
            job, version = self._read(work_id)
            if job is None:
                raise KeyError(work_id)
            if job["claim_token"] is not None and job["lease_until"] > utc_text(now):
                raise WorkBusy("cannot redrive active work")
            job.update(terminal=None, failures={}, claim_token=None, lease_until=None, redriven_at=utc_text(now))
            if self._transact([self._state_put(job, version)]):
                return
        raise WorkBusy("redrive contention")
