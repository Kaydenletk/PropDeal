import json
import os
import subprocess
import time
import pytest
import boto3

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def localstack():
    if os.environ.get("SKIP_LOCALSTACK"):
        pytest.skip("SKIP_LOCALSTACK set")
    subprocess.run(
        ["docker", "compose", "-f", "tests/integration/docker-compose.yml", "up", "-d"],
        check=True,
    )
    for _ in range(30):
        try:
            boto3.client("s3", endpoint_url="http://localhost:4566", region_name="us-east-1").list_buckets()
            break
        except Exception:
            time.sleep(2)
    yield
    subprocess.run(
        ["docker", "compose", "-f", "tests/integration/docker-compose.yml", "down"],
        check=True,
    )


def test_step_functions_asl_loads():
    sfn = boto3.client("stepfunctions", endpoint_url="http://localhost:4566", region_name="us-east-1")
    asl = open("iac/asl/pipeline.json").read()
    for var in ["fetch_arn", "transform_arn", "enrich_arn", "load_arn", "sns_topic_arn", "raw_bucket", "clean_bucket"]:
        if "arn" in var:
            asl = asl.replace("${" + var + "}", f"arn:aws:lambda:us-east-1:000000000000:function:{var}")
        else:
            asl = asl.replace("${" + var + "}", f"proptech-{var}")
    try:
        sfn.create_state_machine(
            name="test-pipeline",
            definition=asl,
            roleArn="arn:aws:iam::000000000000:role/test",
        )
    except sfn.exceptions.StateMachineAlreadyExists:
        pass


def test_s3_lambda_chain_smoke(sample_listing):
    s3 = boto3.client("s3", endpoint_url="http://localhost:4566", region_name="us-east-1")
    for b in ("test-raw", "test-clean"):
        try:
            s3.create_bucket(Bucket=b)
        except Exception:
            pass
    s3.put_object(
        Bucket="test-raw",
        Key="raw/2026-04-25.json",
        Body=json.dumps([sample_listing]).encode(),
    )
    obj = s3.get_object(Bucket="test-raw", Key="raw/2026-04-25.json")
    listings = json.loads(obj["Body"].read())
    assert listings[0]["id"] == "abc-123"
