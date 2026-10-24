"""Observe NEW device readings via HTTP without generating simulated data."""
import argparse
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--device", default="UM1")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=45)
    args = parser.parse_args()
    if args.samples < 1 or args.timeout <= 0:
        parser.error("--samples y --timeout deben ser positivos")

    def get(path):
        with urlopen(args.url.rstrip("/") + path, timeout=5) as response:
            return json.load(response)

    device = next((d for d in get("/api/v1/devices") if d["device_code"] == args.device), None)
    if not device:
        raise SystemExit(f"Dispositivo {args.device} no registrado")
    path = "/api/v1/readings/latest?" + urlencode({"device_id": device["id"]})
    latest = get(path)
    baseline = latest["id"] if latest else 0
    print(f"Esperando {args.samples} mediciones NUEVAS de {args.device}; ultima ID={baseline}", flush=True)
    seen = set()
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        latest = get(path)
        if latest and latest["id"] > baseline and latest["id"] not in seen:
            seen.add(latest["id"])
            print(f"ID={latest['id']} temperatura={latest['temperature_c']} C "
                  f"humedad={latest['humidity_percent']} % recepcion={latest['received_at']}", flush=True)
            if len(seen) >= args.samples:
                print("Captura HTTP de nuevas mediciones verificada.")
                return 0
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    if latest:
        received = datetime.fromisoformat(latest["received_at"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - received).total_seconds()
        print(f"Ultima recepcion hace {age:.0f} s.")
    print(f"Verificacion incompleta: {len(seen)}/{args.samples} mediciones nuevas. "
          "Comprobar alimentacion, Wi-Fi, sensor y resultado POST en el ESP32.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
