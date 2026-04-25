import json
import boto3

_CACHE: dict[str, dict] = {}
_SM = boto3.client("secretsmanager")


def get_secret(name: str) -> dict:
    if name in _CACHE:
        return _CACHE[name]
    resp = _SM.get_secret_value(SecretId=name)
    val = json.loads(resp["SecretString"])
    _CACHE[name] = val
    return val
