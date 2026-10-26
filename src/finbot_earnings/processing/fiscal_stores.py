"""Identical version-2 layout in SQLite and DynamoDB; legacy namespaces untouched."""
import sqlite3
from pathlib import Path
import uuid

from .contracts import json_text, json_value
from .errors import TechnicalFailure, WorkConflict
from .fiscal_repository import FiscalRepository


class SQLiteFiscalRepository(FiscalRepository):
    def __init__(self, path, **kwargs):
        super().__init__(**kwargs)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS fiscal_v2_items (pk TEXT, sk TEXT, item_json TEXT NOT NULL, PRIMARY KEY(pk,sk))")

    def close(self):
        self.db.close()

    def _get(self, pk, sk):
        row = self.db.execute("SELECT item_json FROM fiscal_v2_items WHERE pk=? AND sk=?", (pk, sk)).fetchone()
        return None if row is None else json_value(row[0])

    def _immutable(self, item):
        self.db.execute("INSERT OR IGNORE INTO fiscal_v2_items VALUES (?,?,?)", (item["pk"], item["sk"], json_text(item)))
        if self._get(item["pk"], item["sk"]) != item:
            raise WorkConflict("immutable key reused with different content")

    def _cas(self, item, prior, token, now, extra, deletes):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            actual = self._get(item["pk"], item["sk"])
            if ((prior is None and actual is not None) or
                (prior is not None and (actual is None or actual["version"] != prior["version"])) or
                (token is not None and (actual["claim_token"] != token or actual["lease_until"] <= now))):
                self.db.execute("ROLLBACK")
                return False
            for value in [item, *extra]:
                self.db.execute("INSERT OR REPLACE INTO fiscal_v2_items VALUES (?,?,?)", (value["pk"], value["sk"], json_text(value)))
            for key in deletes:
                self.db.execute("DELETE FROM fiscal_v2_items WHERE pk=? AND sk=?", (key["pk"], key["sk"]))
            self.db.execute("COMMIT")
            return True
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _query(self, pk, limit, cursor):
        rows = self.db.execute("SELECT item_json FROM fiscal_v2_items WHERE pk=? AND sk>? ORDER BY sk LIMIT ?", (pk, cursor or "", limit + 1)).fetchall()
        items = [json_value(row[0]) for row in rows[:limit]]
        return dict(items=items, cursor=items[-1]["sk"] if len(rows) > limit else None)


class DynamoDBFiscalRepository(FiscalRepository):
    """Injected resource.meta.client with native types, strong reads and CAS writes."""
    def __init__(self, client, table_name, **kwargs):
        super().__init__(**kwargs)
        self.client, self.table_name = client, table_name

    def _get(self, pk, sk):
        return self.client.get_item(TableName=self.table_name, Key=dict(pk=pk, sk=sk), ConsistentRead=True).get("Item")

    def _immutable(self, item):
        from boto3.dynamodb.conditions import Attr
        try:
            self.client.put_item(TableName=self.table_name, Item=item,
                                 **self._condition(Attr("pk").not_exists()))
        except self.client.exceptions.ConditionalCheckFailedException:
            if self._get(item["pk"], item["sk"]) != item:
                raise WorkConflict("immutable key reused with different content") from None

    @staticmethod
    def _condition(expression):
        from boto3.dynamodb.conditions import ConditionExpressionBuilder
        built = ConditionExpressionBuilder().build_expression(expression)
        result = dict(ConditionExpression=built.condition_expression)
        if built.attribute_name_placeholders:
            result["ExpressionAttributeNames"] = built.attribute_name_placeholders
        if built.attribute_value_placeholders:
            result["ExpressionAttributeValues"] = built.attribute_value_placeholders
        return result

    def _cas(self, item, prior, token, now, extra, deletes):
        from boto3.dynamodb.conditions import Attr
        condition = Attr("pk").not_exists() if prior is None else Attr("version").eq(prior["version"])
        if token is not None:
            condition &= Attr("claim_token").eq(token) & Attr("lease_until").gt(now)
        actions = [dict(Put=dict(TableName=self.table_name, Item=item, **self._condition(condition)))]
        actions.extend(dict(Put=dict(TableName=self.table_name, Item=value)) for value in extra)
        actions.extend(dict(Delete=dict(TableName=self.table_name, Key=key)) for key in deletes)
        if any(len(json_text(value).encode("utf-8")) > 380 * 1024 for value in [item, *extra]) or len(json_text(actions).encode("utf-8")) > 3_800_000:
            raise TechnicalFailure("dynamodb_transaction_exceeds_limit", retryable=False)
        try:
            self.client.transact_write_items(TransactItems=actions, ClientRequestToken=uuid.uuid4().hex)
            return True
        except self.client.exceptions.TransactionCanceledException as exc:
            codes = [reason.get("Code") for reason in exc.response.get("CancellationReasons", [])]
            if codes and any(c in {"ConditionalCheckFailed", "TransactionConflict"} for c in codes) and all(c in {None, "None", "ConditionalCheckFailed", "TransactionConflict"} for c in codes):
                return False
            raise

    def _query(self, pk, limit, cursor):
        # One explicit bounded page; continuation belongs to the operator, not a scan.
        request = dict(TableName=self.table_name, KeyConditionExpression="pk = :pk", ExpressionAttributeValues={":pk": pk},
                       ConsistentRead=True, Limit=limit)
        if cursor:
            request["ExclusiveStartKey"] = dict(pk=pk, sk=cursor)
        page = self.client.query(**request)
        return dict(items=page.get("Items", []), cursor=page.get("LastEvaluatedKey", {}).get("sk"))
