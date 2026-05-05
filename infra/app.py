#!/usr/bin/env python3
from aws_cdk import App, Environment

from ohipy_infra.stack import OhipyApiStack

app = App()

OhipyApiStack(
    app,
    "OhipyApiStack",
    env=Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)

app.synth()
