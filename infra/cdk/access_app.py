"""Separate, review-only bootstrap assembly for repository-scoped release access.

Synthesize explicitly; the application release never creates its own deployment roles.
"""
from aws_cdk import App, CfnOutput, Environment, Stack
from aws_cdk import aws_iam as iam


class ReleaseAccessStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, termination_protection=True, **kwargs)
        # Verified via the GitHub OIDC customization API, 2026-10-25. IDs are immutable.
        subject = "repo:ilancooke@8453151/finbot-earnings@1350331204"
        provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(self, "GitHub",
            "arn:aws:iam::559007813222:oidc-provider/token.actions.githubusercontent.com")
        def principal(suffix):
            return iam.OpenIdConnectPrincipal(provider, conditions={"StringEquals": {
                "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                "token.actions.githubusercontent.com:sub": subject + suffix}})
        plan = iam.Role(self, "Plan", role_name="finbot-earnings-github-plan",
            assumed_by=principal(":ref:refs/heads/main"))
        deploy = iam.Role(self, "Deploy", role_name="finbot-earnings-github-deploy",
            assumed_by=principal(":environment:production"))
        plan.add_to_policy(iam.PolicyStatement(actions=["cloudformation:DescribeStacks", "cloudformation:GetTemplate",
            "cloudformation:DescribeStackEvents", "cloudformation:DescribeStackResources"],
            resources=["arn:aws:cloudformation:us-east-1:559007813222:stack/finbot-earnings-prod/*"]))
        for role in (plan, deploy):
            role.add_to_policy(iam.PolicyStatement(actions=["ssm:GetParameter"],
                resources=["arn:aws:ssm:us-east-1:559007813222:parameter/cdk-bootstrap/hnb659fds/version"]))
        deploy.add_to_policy(iam.PolicyStatement(actions=["sts:AssumeRole"], resources=[
            "arn:aws:iam::559007813222:role/cdk-hnb659fds-deploy-role-559007813222-us-east-1",
            "arn:aws:iam::559007813222:role/cdk-hnb659fds-file-publishing-role-559007813222-us-east-1"]))
        CfnOutput(self, "PlanRoleArn", value=plan.role_arn)
        CfnOutput(self, "DeployRoleArn", value=deploy.role_arn)


def main():
    app = App()
    ReleaseAccessStack(app, "finbot-earnings-release-access", env=Environment(account="559007813222", region="us-east-1"))
    app.synth()


if __name__ == "__main__":
    main()
