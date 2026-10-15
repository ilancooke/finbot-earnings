"""All default tests are offline, including AWS SDK credential resolution."""

import socket

import pytest


@pytest.fixture(autouse=True)
def offline_environment(monkeypatch):
    for key, value in {
        "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SESSION_TOKEN": "testing", "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_EC2_METADATA_DISABLED": "true",
    }.items():
        monkeypatch.setenv(key, value)
    def forbidden(*args, **kwargs):
        raise AssertionError("Network access is forbidden in default tests")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
