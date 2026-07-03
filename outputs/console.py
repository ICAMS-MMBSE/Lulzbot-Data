"""Console output for sensor payloads."""

import json


def write_payload(payload):
    print(json.dumps(payload))
