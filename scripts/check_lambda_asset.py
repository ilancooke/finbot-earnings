"""Offline check executed inside the target Lambda container, with only asset imports."""
import io
from pathlib import Path
import sys


def main():
    asset = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(asset))
    # No credentials, sockets or service clients are needed.
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError("network forbidden during Lambda asset verification")
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    import boto3
    import html5lib
    import httpx
    import jsonschema
    import openai
    import pydantic_core
    import jiter
    import rpds
    from PIL import Image
    from finbot_earnings.processing import lambda_handler, fiscal_runtime
    from finbot_earnings.processing.fiscal.config import digest, load_config
    from finbot_earnings.processing.fiscal.html_text import plain_text_preview
    for module in (boto3, html5lib, httpx, jsonschema, openai, pydantic_core, jiter, rpds, Image,
                   lambda_handler, fiscal_runtime):
        assert Path(module.__file__).resolve().is_relative_to(asset), module.__name__
    assert digest(load_config()) == "e871d66c10ec2be3458efd113617e19b4e53726de68791c5053a4bb8cae15097"
    for format in ("JPEG", "PNG", "GIF"):
        data = io.BytesIO()
        Image.new("RGB", (3, 2), "red").save(data, format=format)
        data.seek(0)
        with Image.open(data) as image:
            image.load()
            assert image.size == (3, 2) and image.format == format
    assert "1.23" in plain_text_preview(b"<html><body><table><tr><td>EPS</td><td>1.23</td></tr></table></body></html>")
    print("Lambda asset imports, frozen identities, HTML parser and JPEG/PNG/GIF decoders verified offline")


if __name__ == "__main__":
    main()
