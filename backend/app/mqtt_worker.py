"""Single persistent MQTT consumer; application ACK only after SQL + CSV commit."""
import json
import logging
from pathlib import Path
import signal
import sys
from fastapi import HTTPException
import paho.mqtt.client as mqtt
from pydantic import ValidationError
from sqlalchemy import text
from app.core.config import settings
from app.core.database import Session
from app.services.mqtt_ingestion import process_message

READY = Path("/tmp/rutasalud-mqtt-ready")
LOG = logging.getLogger("rutasalud.mqtt")


def on_connect(client, userdata, flags, reason_code, properties):
    READY.unlink(missing_ok=True)
    if reason_code.is_failure:
        LOG.error("Conexion al broker rechazada: %s", reason_code)
        return
    result, _ = client.subscribe("rutasalud/+/telemetria", qos=1)
    if result != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError("No se pudo solicitar suscripcion MQTT")


def on_subscribe(client, userdata, mid, reason_codes, properties):
    if not reason_codes or any(code.is_failure for code in reason_codes):
        raise RuntimeError("Suscripcion MQTT rechazada por el broker")
    READY.touch()
    LOG.info("Suscrito a rutasalud/+/telemetria; QoS 1, sesion persistente")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    READY.unlink(missing_ok=True)
    LOG.warning("Broker desconectado: %s", reason_code)


def on_message(client, userdata, message):
    try:
        if message.retain:
            raise ValueError("La telemetria no admite mensajes retained")
        topic, ack = process_message(message.topic, message.payload)
    except (ValueError, ValidationError):
        LOG.warning("Mensaje rechazado: topic/JSON/identidad/rangos no validos; sin acuse de guardado")
    except HTTPException as error:
        if error.status_code >= 500:
            # No confirmar transporte: al reiniciar se redelivera la sesion persistente.
            raise RuntimeError("Almacenamiento pendiente; se conserva el mensaje MQTT") from error
        LOG.warning("Mensaje rechazado por reglas de negocio: HTTP %s; sin acuse de guardado", error.status_code)
    else:
        info = client.publish(topic, json.dumps(ack), qos=1, retain=False)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError("No se pudo encolar acuse de guardado")
        LOG.info("Guardada unidad=%s id=%s secuencia=%s", ack["device_code"], ack["id"], ack["sequence_number"])
    # Descarta definitivamente los mensajes invalidos para evitar un bucle toxico.
    # Los validos ya estan guardados; si el ACK de aplicacion se pierde, el ESP reintenta.
    result = client.ack(message.mid, message.qos)
    if result != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError("No se pudo confirmar transporte MQTT")


def main():
    if "--healthcheck" in sys.argv:
        if not READY.exists():
            return 1
        with Session() as db:
            db.execute(text("SELECT 1"))
        return 0
    if not settings.mqtt_worker_password:
        raise SystemExit("MQTT no configurado: ejecutar scripts/setup_mqtt.py")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    READY.unlink(missing_ok=True)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rutasalud-ingestor",
                         clean_session=False, protocol=mqtt.MQTTv311, manual_ack=True)
    client.username_pw_set(settings.mqtt_worker_username, settings.mqtt_worker_password)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: client.disconnect())
    client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=60)
    try:
        client.loop_forever(retry_first_connection=True)
    finally:
        READY.unlink(missing_ok=True)
        client.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
