from aws_cdk import ArnFormat, CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cloudwatch as cw, aws_cloudwatch_actions as actions, aws_dynamodb as ddb
from aws_cdk import aws_iam as iam, aws_lambda as function, aws_lambda_event_sources as events
from aws_cdk import aws_logs as logs, aws_sns as sns, aws_sqs as sqs
from aws_cdk import aws_secretsmanager as secrets

from .settings import Settings


class EarningsStack(Stack):
    def __init__(self, scope, construct_id, *, settings: Settings, asset_path, **kwargs):
        super().__init__(scope, construct_id, termination_protection=True, **kwargs)
        prefix = settings.stack_name
        table = ddb.Table(self, "Processing", table_name=prefix, partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING), billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            deletion_protection=True, removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(point_in_time_recovery_enabled=True))
        dead = sqs.Queue(self, "FailedWork", queue_name=prefix + "-failed-work", retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED, enforce_ssl=True, removal_policy=RemovalPolicy.RETAIN)
        delivery_dead = sqs.Queue(self, "FailedDelivery", queue_name=prefix + "-failed-delivery", retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED, enforce_ssl=True, removal_policy=RemovalPolicy.RETAIN)
        queue = sqs.Queue(self, "Filings", queue_name=prefix + "-filings", visibility_timeout=Duration.seconds(1800),
            retention_period=Duration.days(14), encryption=sqs.QueueEncryption.SQS_MANAGED, enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(queue=dead, max_receive_count=5), removal_policy=RemovalPolicy.RETAIN)
        # Own only the subscription and destination policies, not the producer topic.
        for destination in (queue, delivery_dead):
            destination.add_to_resource_policy(iam.PolicyStatement(actions=["sqs:SendMessage"],
                principals=[iam.ServicePrincipal("sns.amazonaws.com")], resources=[destination.queue_arn],
                conditions={"ArnEquals": {"aws:SourceArn": settings.filing_topic_arn},
                            "StringEquals": {"aws:SourceAccount": settings.account}}))
        subscription = sns.CfnSubscription(self, "FilingSubscription", protocol="sqs", endpoint=queue.queue_arn,
            topic_arn=settings.filing_topic_arn, raw_message_delivery=False,
            redrive_policy={"deadLetterTargetArn": delivery_dead.queue_arn})
        subscription.node.add_dependency(queue, delivery_dead)
        output = sns.Topic(self, "ValidatedEarnings", topic_name=prefix + "-validated", enforce_ssl=True)
        # Keep the existing topic construct/name; the event contract is earnings.extracted.
        inspection = sqs.Queue(self, "OutputInspection", queue_name=prefix + "-output",
            retention_period=Duration.days(14), encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True, removal_policy=RemovalPolicy.RETAIN)
        output_dead = sqs.Queue(self, "OutputDeliveryFailed", queue_name=prefix + "-output-delivery-failed",
            retention_period=Duration.days(14), encryption=sqs.QueueEncryption.SQS_MANAGED,
            enforce_ssl=True, removal_policy=RemovalPolicy.RETAIN)
        for destination in (inspection, output_dead):
            destination.add_to_resource_policy(iam.PolicyStatement(actions=["sqs:SendMessage"],
                principals=[iam.ServicePrincipal("sns.amazonaws.com")], resources=[destination.queue_arn],
                conditions={"ArnEquals": {"aws:SourceArn": output.topic_arn},
                            "StringEquals": {"aws:SourceAccount": settings.account}}))
        output_subscription = sns.CfnSubscription(self, "OutputSubscription", protocol="sqs",
            endpoint=inspection.queue_arn, topic_arn=output.topic_arn, raw_message_delivery=True,
            redrive_policy={"deadLetterTargetArn": output_dead.queue_arn})
        output_subscription.node.add_dependency(inspection, output_dead)
        # CfnSecret without a value creates an empty secret, never a random credential.
        secret = secrets.CfnSecret(self, "OpenAIProjectKey", name=settings.openai_secret_name,
            description="Earnings-owned OpenAI project credential; populate securely before activation")
        secret.apply_removal_policy(RemovalPolicy.RETAIN)
        alarms = sns.Topic(self, "AlarmNotifications", topic_name=prefix + "-alarms", enforce_ssl=True)
        sns.CfnSubscription(self, "AlarmEmail", protocol="email", endpoint=settings.alarm_email,
                            topic_arn=alarms.topic_arn)
        group = logs.LogGroup(self, "Logs", log_group_name="/finbot/" + prefix,
                              retention=logs.RetentionDays.ONE_MONTH, removal_policy=RemovalPolicy.RETAIN)
        role = iam.Role(self, "WorkerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
        group.grant_write(role)
        role.add_to_policy(iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
            "dynamodb:ConditionCheckItem", "dynamodb:DeleteItem", "dynamodb:Query"], resources=[table.table_arn]))
        role.add_to_policy(iam.PolicyStatement(actions=["s3:GetObject"],
            resources=[f"arn:{self.partition}:s3:::{settings.source_bucket}/*"]))
        if settings.source_kms_key_arn:
            role.add_to_policy(iam.PolicyStatement(actions=["kms:Decrypt"], resources=[settings.source_kms_key_arn],
                conditions={"StringEquals": {"kms:ViaService": f"s3.{settings.region}.amazonaws.com"}}))
        role.add_to_policy(iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"], resources=[secret.ref]))
        # Unattached policies: the operator explicitly selects read-only or recovery access.
        inspection_policy = iam.ManagedPolicy(self, "OperatorInspection", statements=[
            iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:Query"], resources=[table.table_arn]),
            iam.PolicyStatement(actions=["sqs:ReceiveMessage", "sqs:GetQueueAttributes"], resources=[inspection.queue_arn]),
        ])
        recovery_policy = iam.ManagedPolicy(self, "OperatorRecovery", statements=[
            iam.PolicyStatement(actions=["dynamodb:GetItem", "dynamodb:Query", "dynamodb:PutItem",
                "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:ConditionCheckItem"], resources=[table.table_arn]),
            iam.PolicyStatement(actions=["s3:GetObject"], resources=[f"arn:{self.partition}:s3:::{settings.source_bucket}/*"]),
            iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"], resources=[secret.ref]),
            iam.PolicyStatement(actions=["sns:Publish"], resources=[output.topic_arn]),
        ])
        if settings.source_kms_key_arn:
            recovery_policy.add_statements(iam.PolicyStatement(actions=["kms:Decrypt"], resources=[settings.source_kms_key_arn],
                conditions={"StringEquals": {"kms:ViaService": f"s3.{settings.region}.amazonaws.com"}}))
        worker = function.Function(self, "Worker", function_name=prefix, runtime=function.Runtime.PYTHON_3_13,
            architecture=function.Architecture.X86_64, code=function.Code.from_asset(str(asset_path)), role=role,
            handler="finbot_earnings.processing.lambda_handler.handler", timeout=Duration.seconds(300), memory_size=1024,
            reserved_concurrent_executions=2, logging_format=function.LoggingFormat.JSON, log_group=group,
            application_log_level_v2=function.ApplicationLogLevel.INFO,
            current_version_options=function.VersionOptions(removal_policy=RemovalPolicy.RETAIN),
            environment={"EARNINGS_TABLE_NAME": table.table_name, "EARNINGS_SOURCE_BUCKET": settings.source_bucket,
                "EARNINGS_TOPIC_ARN": output.topic_arn, "EARNINGS_QUEUE_ARN": queue.queue_arn,
                "FILING_READY_TOPIC_ARN": settings.filing_topic_arn,
                "EARNINGS_FISCAL_CONFIG_SHA256": settings.fiscal_config_sha256,
                "EARNINGS_OPENAI_SECRET_ARN": secret.ref})
        output.grant_publish(role)
        alias = function.Alias(self, "Production", alias_name="production", version=worker.current_version)
        alias.add_event_source(events.SqsEventSource(queue, batch_size=1, report_batch_item_failures=True,
                                                     max_concurrency=2, enabled=settings.consumption_enabled))
        failed_metric = logs.MetricFilter(self, "ProcessingFailures", log_group=group,
            filter_pattern=logs.FilterPattern.string_value("$.message", "=", "Filing message deferred"),
            metric_namespace=prefix, metric_name="ProcessingFailures", metric_value="1", default_value=0)
        outcome_metric = logs.MetricFilter(self, "UnacknowledgedWork", log_group=group,
            filter_pattern=logs.FilterPattern.any(
                logs.FilterPattern.string_value("$.outcome", "=", "processing_failed"),
                logs.FilterPattern.string_value("$.outcome", "=", "retry")),
            metric_namespace=prefix, metric_name="UnacknowledgedWork", metric_value="1", default_value=0)
        for name, metric, threshold in (
            ("FailedWorkPresent", dead.metric_approximate_number_of_messages_visible(), 1),
            ("FailedDeliveryPresent", delivery_dead.metric_approximate_number_of_messages_visible(), 1),
            ("InputAge", queue.metric_approximate_age_of_oldest_message(), 900),
            ("WorkerErrors", worker.metric_errors(statistic="Sum", period=Duration.minutes(5)), 1),
            ("WorkerThrottles", worker.metric_throttles(statistic="Sum", period=Duration.minutes(5)), 1),
            ("ProcessingFailure", failed_metric.metric(statistic="Sum", period=Duration.minutes(5)), 1),
            ("Unacknowledged", outcome_metric.metric(statistic="Sum", period=Duration.minutes(5)), 1),
            ("OutputDeliveryDead", output_dead.metric_approximate_number_of_messages_visible(), 1),
            ("OutputDeliveryFailure", output.metric_number_of_notifications_failed(statistic="Sum", period=Duration.minutes(5)), 1),
        ):
            alarm_name = prefix + "-" + name
            alarms.add_to_resource_policy(iam.PolicyStatement(actions=["sns:Publish"],
                principals=[iam.ServicePrincipal("cloudwatch.amazonaws.com")], resources=[alarms.topic_arn],
                conditions={"StringEquals": {"aws:SourceAccount": settings.account},
                    "ArnEquals": {"aws:SourceArn": self.format_arn(service="cloudwatch", resource="alarm",
                        resource_name=alarm_name, arn_format=ArnFormat.COLON_RESOURCE_NAME)}}))
            alarm = cw.Alarm(self, name, alarm_name=alarm_name, metric=metric, threshold=threshold, evaluation_periods=1,
                comparison_operator=cw.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cw.TreatMissingData.NOT_BREACHING)
            alarm.add_alarm_action(actions.SnsAction(alarms))
        for name, value in {
            "InputQueueUrl": queue.queue_url, "InputQueueArn": queue.queue_arn,
            "FailedWorkQueueUrl": dead.queue_url, "FailedDeliveryQueueUrl": delivery_dead.queue_url,
            "ProcessingTable": table.table_name, "ValidatedTopicArn": output.topic_arn,
            "AlarmTopicArn": alarms.topic_arn, "ProductionAliasArn": alias.function_arn,
            "LambdaVersion": worker.current_version.version, "LogGroup": group.log_group_name,
            "OpenAISecretArn": secret.ref, "OutputQueueUrl": inspection.queue_url,
            "OutputQueueArn": inspection.queue_arn, "OutputDeliveryFailedQueueUrl": output_dead.queue_url,
            "OperatorInspectionPolicyArn": inspection_policy.managed_policy_arn,
            "OperatorRecoveryPolicyArn": recovery_policy.managed_policy_arn,
            "ConsumptionEnabled": str(settings.consumption_enabled).lower(),
        }.items():
            CfnOutput(self, name, value=value)
