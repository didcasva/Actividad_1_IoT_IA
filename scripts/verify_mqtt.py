"""Integration check with SYNTHETIC MQTT data: use only a disposable test deployment."""
import argparse
import csv
import json
import os
from pathlib import Path
import queue
import threading
import time
import uuid
import paho.mqtt.client as mqtt
from sqlalchemy import select
from app.core.config import settings
from app.core.database import Session
from app.models.entities import Device, SensorReading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-test-data", action="store_true")
    parser.add_argument("--publish-only", action="store_true", help="Publica sin esperar receptor, para ensayar recuperacion")
    parser.add_argument("--boot-id", default="mqtt-integration-" + uuid.uuid4().hex)
    args = parser.parse_args()
    if not args.allow_test_data:
        parser.error("Requiere --allow-test-data y una instalacion separada del historico fisico")
    device = os.environ.get("MQTT_DEVICE_CODE", "UM1")
    if not args.publish_only:
        with Session() as db:
            if not db.scalar(select(Device).where(Device.device_code == device)):
                raise SystemExit("Registrar la unidad de prueba en devices antes de ejecutar")
    ready = threading.Event()
    received = queue.Queue()
    observed = queue.Queue()
    observer_ready = threading.Event()
    prefix = f"rutasalud/{device}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="verify-device-" + uuid.uuid4().hex[:12])
    client.username_pw_set(os.environ["MQTT_DEVICE_USERNAME"], os.environ["MQTT_DEVICE_PASSWORD"])

    def on_connect(c, userdata, flags, reason, properties):
        if reason.is_failure:
            return
        c.subscribe(prefix + "/ack", qos=1)

    client.on_connect = on_connect
    client.on_subscribe = lambda *a: ready.set()
    client.on_message = lambda c, u, msg: received.put(json.loads(msg.payload))
    client.connect(settings.mqtt_host, settings.mqtt_port)
    client.loop_start()
    observer = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="verify-observer-" + uuid.uuid4().hex[:12])
    observer.username_pw_set(settings.mqtt_worker_username, settings.mqtt_worker_password)
    observer.on_connect = lambda c, u, f, r, p: c.subscribe("rutasalud/+/telemetria", qos=1) if not r.is_failure else None
    observer.on_subscribe = lambda *a: observer_ready.set()
    observer.on_message = lambda c, u, msg: observed.put((msg.topic, msg.payload))
    observer.connect(settings.mqtt_host, settings.mqtt_port)
    observer.loop_start()
    try:
        assert ready.wait(10) and observer_ready.wait(10), "No se confirmo suscripcion"
        body = dict(device_code=device, temperature_c=26.4, humidity_percent=58,
                    measured_at=None, boot_id=args.boot_id, sequence_number=0)

        def publish(topic, data):
            info = client.publish(topic, json.dumps(data) if isinstance(data, dict) else data, qos=1, retain=False)
            info.wait_for_publish(timeout=10)
            assert info.is_published(), "El broker no confirmo la publicacion"

        def wait_ack():
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                ack = received.get(timeout=max(.1, deadline - time.monotonic()))
                if ack.get("boot_id") == args.boot_id:
                    assert ack["status"] == "stored" and ack["sequence_number"] == 0
                    return ack
            raise AssertionError("Sin acuse de guardado")

        publish(prefix + "/telemetria", body)
        if args.publish_only:
            print(f"SIMULACION publicada sin esperar guardado: boot_id={args.boot_id}")
            return
        first = wait_ack()
        for _ in range(2):
            publish(prefix + "/telemetria", body)
            assert wait_ack()["id"] == first["id"], "Un reintento genero otra fila"
        with Session() as db:
            rows = list(db.scalars(select(SensorReading).where(SensorReading.boot_id == args.boot_id)))
            assert len(rows) == 1 and rows[0].id == first["id"]
        with Path(settings.csv_path).open(newline="", encoding="utf-8") as stream:
            rows = [row for row in csv.DictReader(stream) if row["boot_id"] == args.boot_id]
            assert len(rows) == 1 and int(rows[0]["id"]) == first["id"]
        print("OK: MQTT -> receptor -> PostgreSQL + CSV; ACK de guardado; reintentos sin duplicados.")
        # Confirmar que el observador funciona antes de probar una publicacion prohibida.
        seen = []
        while not observed.empty():
            seen.append(observed.get_nowait()[0])
        assert prefix + "/telemetria" in seen
        publish("rutasalud/UNAUTHORIZED/telemetria", body | {"device_code": "UNAUTHORIZED"})
        time.sleep(1)
        assert observed.empty(), "La ACL permitio publicar en otra unidad"
        print("OK: ACL impide que el dispositivo publique en otra unidad.")
        while not received.empty():
            received.get_nowait()
        publish(prefix + "/telemetria", body | {"device_code": "OTHER", "sequence_number": 1})
        publish(prefix + "/telemetria", "{broken")
        time.sleep(1)
        assert received.empty(), "Se confirmo como guardado un mensaje invalido"
        with Session() as db:
            assert len(list(db.scalars(select(SensorReading).where(SensorReading.boot_id == args.boot_id)))) == 1
        print("OK: JSON invalido y discrepancia topic/device_code rechazados sin insertar ni confirmar guardado.")
        publish(prefix + "/ack", first)
        time.sleep(1)
        assert received.empty(), "La ACL permitio al dispositivo falsificar un ACK de guardado"
        print("OK: el dispositivo no puede publicar confirmaciones de guardado.")
        for username, password in [(None, None), (os.environ["MQTT_DEVICE_USERNAME"], "incorrect-password")]:
            rejected = threading.Event()
            reason_codes = []
            bad = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="verify-denied-" + uuid.uuid4().hex[:12])
            if username:
                bad.username_pw_set(username, password)

            def connected(c, u, f, reason, p):
                reason_codes.append(reason)
                rejected.set()

            bad.on_connect = connected
            bad.connect(settings.mqtt_host, settings.mqtt_port)
            bad.loop_start()
            try:
                assert rejected.wait(5) and reason_codes[0].is_failure, "Conexion no autorizada aceptada"
            finally:
                bad.disconnect()
                bad.loop_stop()
        print("OK: conexiones anonimas y contrasena incorrecta rechazadas.")
    finally:
        client.disconnect()
        client.loop_stop()
        observer.disconnect()
        observer.loop_stop()


if __name__ == "__main__":
    main()
