import json
import logging
import os
import sys
import time
import uuid

_LAMBDA_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "local")
_LOGGER = logging.getLogger("proptech")
_LOGGER.setLevel(logging.INFO)
if not _LOGGER.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(h)


def log(level: str, msg: str, **kw):
    payload = {
        "ts": time.time(),
        "level": level,
        "lambda": _LAMBDA_NAME,
        "request_id": kw.pop("request_id", None) or os.environ.get("AWS_REQUEST_ID", str(uuid.uuid4())),
        "msg": msg,
        **kw,
    }
    _LOGGER.info(json.dumps(payload, default=str))
