"""Provision LAN MQTT without overwriting HTTP/DB secrets or printing passwords."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="IP LAN o DNS del servidor, sin esquema ni ruta")
    parser.add_argument("--device", default="UM1")
    parser.add_argument("--sudo-docker", action="store_true", help="Invocar sudo docker en Ubuntu sin cambiar el propietario de los archivos")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,252}", args.host):
        parser.error("--host debe ser una IP o nombre DNS, sin http:// ni puerto")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.device):
        parser.error("--device solo admite letras, numeros, guion y guion bajo")
    env = Path(".env")
    if not env.exists():
        parser.error("Ejecutar primero python scripts/setup_env.py desde la raiz del proyecto")
    original = env.read_text(encoding="utf-8-sig")
    values = dict(line.split("=", 1) for line in original.splitlines()
                  if "=" in line and not line.lstrip().startswith("#"))
    if values.get("MQTT_DEVICE_CODE", args.device) != args.device:
        parser.error("Esta instalacion ya tiene otra unidad MQTT. No se reemplazan sus permisos.")
    desired = {
        "MQTT_PORT": "1883",
        "MQTT_WORKER_USERNAME": "rutasalud-worker",
        "MQTT_WORKER_PASSWORD": secrets.token_hex(24),
        "MQTT_DEVICE_CODE": args.device,
        "MQTT_DEVICE_USERNAME": "device-" + args.device,
        "MQTT_DEVICE_PASSWORD": secrets.token_hex(24),
    }
    selected = {key: values.get(key, value) for key, value in desired.items()}
    for key in ("MQTT_WORKER_USERNAME", "MQTT_DEVICE_USERNAME"):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", selected[key]):
            parser.error(f"Valor no admitido en {key}")
    if selected["MQTT_WORKER_USERNAME"] == selected["MQTT_DEVICE_USERNAME"]:
        parser.error("El receptor y el dispositivo necesitan usuarios diferentes")
    for key in ("MQTT_WORKER_PASSWORD", "MQTT_DEVICE_PASSWORD"):
        if selected[key].lower().startswith(("replace_", "reemplazar")):
            parser.error(f"{key} contiene un marcador de ejemplo: eliminar esa linea de .env y repetir para generar una clave")
        if len(selected[key]) < 24 or not re.fullmatch(r"[A-Za-z0-9_-]+", selected[key]):
            parser.error(f"{key} debe tener al menos 24 caracteres alfanumericos, guion o guion bajo")
    port = int(selected["MQTT_PORT"])
    if not 1 <= port <= 65535:
        parser.error("MQTT_PORT debe estar entre 1 y 65535")
    directory = Path(".secrets/mosquitto")
    directory.mkdir(parents=True, exist_ok=True)
    Path(".secrets").chmod(0o700)
    directory.chmod(0o755)  # El directorio montado debe ser legible por mosquitto (UID 1883).
    temporary = directory / "passwords.new"
    try:
        temporary.write_text(
            f"{selected['MQTT_WORKER_USERNAME']}:{selected['MQTT_WORKER_PASSWORD']}\n"
            f"{selected['MQTT_DEVICE_USERNAME']}:{selected['MQTT_DEVICE_PASSWORD']}\n", encoding="utf-8")
        temporary.chmod(0o600)
        # La clave viaja en un archivo privado, nunca como argumento del proceso.
        docker_command = ["sudo", "docker"] if args.sudo_docker else ["docker"]
        subprocess.run(docker_command + ["run", "--rm", "--user", "0:0", "--entrypoint", "mosquitto_passwd",
                        "--mount", f"type=bind,src={directory.resolve()},dst=/work",
                        "eclipse-mosquitto:2.0", "-U", "/work/passwords.new"], check=True)
        temporary.chmod(0o644)  # Solo hashes; el contenedor no recibe .env.
        os.replace(temporary, directory / "passwords")
    finally:
        temporary.unlink(missing_ok=True)
    (directory / "acl").write_text(
        f"user {selected['MQTT_WORKER_USERNAME']}\n"
        "topic read rutasalud/+/telemetria\ntopic write rutasalud/+/ack\n\n"
        f"user {selected['MQTT_DEVICE_USERNAME']}\n"
        f"topic write rutasalud/{args.device}/telemetria\n"
        f"topic write rutasalud/{args.device}/estado\n"
        f"topic read rutasalud/{args.device}/ack\n", encoding="utf-8")
    (directory / "acl").chmod(0o644)
    additions = "".join(f"{key}={value}\n" for key, value in selected.items() if key not in values)
    if additions:
        env.write_text(original.rstrip("\n") + "\n" + additions, encoding="utf-8")
    env.chmod(0o600)
    config = Path("firmware/esp32_dht_monitor/mqtt.config.h")
    config.write_text(
        "#pragma once\n// Generado localmente. No publicar. LAN de laboratorio.\n"
        f"#define MQTT_HOST {json.dumps(args.host)}\n#define MQTT_PORT {port}\n"
        f"#define MQTT_USERNAME {json.dumps(selected['MQTT_DEVICE_USERNAME'])}\n"
        f"#define MQTT_PASSWORD {json.dumps(selected['MQTT_DEVICE_PASSWORD'])}\n"
        "#define MQTT_TLS 0\n", encoding="utf-8")
    config.chmod(0o600)
    print(f"MQTT preparado para {args.device} en {args.host}:{port}; credenciales no impresas.")
    print("Se conservaron las claves HTTP/BD. Registro de la unidad en la BD: seguir docs/mqtt.md.")
    print("Iniciar: docker compose --profile mqtt up -d --build")
    print("Instalar MQTT by Joel Gaehwiler en Arduino IDE, compilar y cargar el firmware para usar MQTT.")


if __name__ == "__main__":
    main()
