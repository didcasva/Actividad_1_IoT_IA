"""Simulador HTTP sin dependencias externas; API_KEY se toma del entorno."""
import argparse
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://localhost:8000")
parser.add_argument("--device", default="esp32-01")
parser.add_argument("--count", type=int, default=10)
parser.add_argument("--interval", type=float, default=10)
args = parser.parse_args()
boot = str(uuid.uuid4())
for seq in range(args.count):
    body = json.dumps(dict(device_code=args.device, boot_id=boot, sequence_number=seq,
        measured_at=datetime.now(timezone.utc).isoformat(), temperature_c=25+2*math.sin(seq), humidity_percent=60+5*math.cos(seq))).encode()
    for attempt in range(6):
        try:
            req = Request(args.url+"/api/v1/readings", data=body, headers={"Content-Type":"application/json", "X-API-Key":os.environ["API_KEY"]})
            with urlopen(req, timeout=10) as response:
                print(response.status, response.read().decode())
            break
        except URLError:
            if attempt == 5:
                raise
            time.sleep(min(2**attempt, 30))
    time.sleep(args.interval)
