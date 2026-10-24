"""Create separate AWS credentials, broker ACL and a TLS firmware configuration."""
import argparse
import getpass
import ipaddress
import json
from pathlib import Path
import re
import secrets
from urllib.parse import quote, urlparse
from urllib.request import urlopen
from aws_common import ROOT, ENV_FILE, docker_command, private_write, read_env, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-ip", required=True)
    parser.add_argument("--db-host", required=True)
    parser.add_argument("--device", default="UM1")
    parser.add_argument("--db-password-file", type=Path)
    parser.add_argument("--ca-file", type=Path, help="CA de pruebas; en AWS se descargan las raices oficiales ISRG")
    parser.add_argument("--sudo-docker", action="store_true")
    args = parser.parse_args()
    if ipaddress.ip_address(args.public_ip).version != 4:
        parser.error("Usar la IPv4 elastica")
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", args.db_host):
        parser.error("--db-host debe ser la IP o DNS privado de PostgreSQL")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", args.device):
        parser.error("Codigo de dispositivo no admitido")
    docker = docker_command(args.sudo_docker)
    if ENV_FILE.exists():
        values = read_env()
        if (values.get("PUBLIC_IP") != args.public_ip or values.get("MQTT_DEVICE_CODE") != args.device
                or urlparse(values.get("DATABASE_URL", "")).hostname != args.db_host):
            parser.error("La configuracion AWS existente tiene otro destino/unidad; se conserva sin sobrescribir")
        print("Se conserva deploy/aws-app/.env y sus credenciales.")
    else:
        password = args.db_password_file.read_text(encoding="utf-8-sig").strip() if args.db_password_file else getpass.getpass("MONITOR_PASSWORD del servidor privado (no se muestra): ")
        if not password or "\n" in password or "\r" in password:
            parser.error("La clave de PostgreSQL debe ser una sola linea no vacia")
        values = {
            "PUBLIC_IP": args.public_ip,
            "DATABASE_URL": f"postgresql+psycopg://monitor:{quote(password, safe='')}@{args.db_host}:5432/monitor",
            "API_KEY": secrets.token_hex(32),
            "DASHBOARD_USERNAME": "rutasalud", "DASHBOARD_PASSWORD": secrets.token_hex(16),
            "MQTT_WORKER_USERNAME": "rutasalud-worker", "MQTT_WORKER_PASSWORD": secrets.token_hex(24),
            "MQTT_DEVICE_CODE": args.device,
            "MQTT_DEVICE_USERNAME": "device-" + args.device, "MQTT_DEVICE_PASSWORD": secrets.token_hex(24),
            "API_LOOPBACK_PORT": "8000", "HTTP_PORT": "80", "HTTPS_PORT": "443", "MQTT_TLS_PORT": "8883",
        }
    result = run(docker + ["run", "--rm", "-i", "caddy:2", "caddy", "hash-password", "--bcrypt-cost", "12"],
                 input=values["DASHBOARD_PASSWORD"].encode("utf-8") + b"\n", capture_output=True)
    values["DASHBOARD_PASSWORD_HASH"] = result.stdout.decode("ascii").strip()
    if not values["DASHBOARD_PASSWORD_HASH"].startswith("$2"):
        raise SystemExit("Caddy no genero un hash bcrypt valido")
    body = "".join(f"{key}='{value}'\n" if "$" in value else f"{key}={value}\n" for key, value in values.items())
    private_write(ENV_FILE, body)
    secret_dir = ROOT / ".secrets"
    secret_dir.mkdir(exist_ok=True)
    secret_dir.chmod(0o700)
    broker = secret_dir / "aws-mosquitto"
    broker.mkdir(exist_ok=True)
    broker.chmod(0o755)
    temporary = broker / "passwords.new"
    try:
        private_write(temporary, f"{values['MQTT_WORKER_USERNAME']}:{values['MQTT_WORKER_PASSWORD']}\n"
                                f"{values['MQTT_DEVICE_USERNAME']}:{values['MQTT_DEVICE_PASSWORD']}\n")
        run(docker + ["run", "--rm", "--user", "0:0", "--entrypoint", "mosquitto_passwd", "--mount",
                      f"type=bind,src={broker},dst=/work", "eclipse-mosquitto:2.0", "-U", "/work/passwords.new"])
        temporary.chmod(0o644)
        temporary.replace(broker / "passwords")
    finally:
        temporary.unlink(missing_ok=True)
    (broker / "acl").write_text(
        f"user {values['MQTT_WORKER_USERNAME']}\ntopic read rutasalud/+/telemetria\ntopic write rutasalud/+/ack\n\n"
        f"user {values['MQTT_DEVICE_USERNAME']}\ntopic write rutasalud/{args.device}/telemetria\n"
        f"topic write rutasalud/{args.device}/estado\ntopic read rutasalud/{args.device}/ack\n", encoding="utf-8")
    (broker / "acl").chmod(0o644)
    ca_path = secret_dir / "aws-ca.pem"
    if args.ca_file:
        ca = args.ca_file.read_text(encoding="ascii")
    elif ca_path.exists():
        ca = ca_path.read_text(encoding="ascii")
    else:
        ca = ""
        for url in ("https://letsencrypt.org/certs/isrgrootx1.pem", "https://letsencrypt.org/certs/isrg-root-x2.pem"):
            with urlopen(url, timeout=20) as response:
                ca += response.read().decode("ascii").strip() + "\n"
    if "-----BEGIN CERTIFICATE-----" not in ca:
        raise SystemExit("La CA no contiene un certificado PEM")
    private_write(ca_path, ca)
    private_write(secret_dir / "aws-firmware/mqtt.config.h",
                  "#pragma once\n// Configuracion AWS privada: copiar junto al sketch solo al migrar el dispositivo.\n"
                  + f"#define MQTT_HOST {json.dumps(values['PUBLIC_IP'])}\n"
                  + f"#define MQTT_PORT {int(values['MQTT_TLS_PORT'])}\n"
                  + f"#define MQTT_USERNAME {json.dumps(values['MQTT_DEVICE_USERNAME'])}\n"
                  + f"#define MQTT_PASSWORD {json.dumps(values['MQTT_DEVICE_PASSWORD'])}\n#define MQTT_TLS 1\n"
                  + '#define MQTT_CA_CERT R"RSCA(\n' + ca + ')RSCA"\n')
    print("AWS preparado: claves no impresas; se conserva intacta la configuracion LAN.")
    print("Archivo privado de acceso web: deploy/aws-app/.env (DASHBOARD_USERNAME / DASHBOARD_PASSWORD).")
    print("Firmware TLS: .secrets/aws-firmware/mqtt.config.h; DEVICE_CODE debe ser " + args.device)
    print("Antes de iniciar la aplicacion: solicitar e instalar el certificado con scripts/aws_certificate.py.")


if __name__ == "__main__":
    main()
