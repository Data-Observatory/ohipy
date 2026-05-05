from pathlib import Path

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_apigatewayv2 as apigwv2
from aws_cdk import aws_apigatewayv2_integrations as apigw_integrations
from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class OhipyApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repo_root = str(Path(__file__).resolve().parents[2])

        scores_function = _lambda.DockerImageFunction(
            self,
            "OhiScoresFunction",
            function_name="ohipy-scores",
            code=_lambda.DockerImageCode.from_image_asset(
                directory=repo_root,
                file="infra/docker/lambda/Dockerfile",
                # Keep the Docker build context small to avoid CDK/jsii OOM during asset hashing.
                exclude=[
                    ".git",
                    "chl",
                    "tests",
                    "infra/cdk.out",
                    "infra/.venv",
                    "infra/.venv313",
                    "infra/node_modules",
                    "**/__pycache__",
                    "**/*.pyc",
                ],
            ),
            architecture=_lambda.Architecture.X86_64,
            memory_size=2048,
            timeout=Duration.seconds(30),
        )

        http_api = apigwv2.HttpApi(
            self,
            "OhiHttpApi",
            create_default_stage=False,
            cors_preflight=apigwv2.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigwv2.CorsHttpMethod.POST, apigwv2.CorsHttpMethod.OPTIONS],
                allow_headers=["content-type"],
            ),
        )

        integration = apigw_integrations.HttpLambdaIntegration(
            "ScoresLambdaIntegration",
            handler=scores_function,
        )

        http_api.add_routes(
            path="/ohi/scores",
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
        )

        stage = apigwv2.HttpStage(
            self,
            "OhiV1Stage",
            http_api=http_api,
            stage_name="v1",
            auto_deploy=True,
        )

        CfnOutput(self, "ApiBaseUrl", value=stage.url)
        CfnOutput(self, "ScoresEndpoint", value=f"{stage.url}ohi/scores")
