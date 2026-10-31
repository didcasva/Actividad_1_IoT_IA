"""Create separate AWS credentials and an HTTPS firmware configuration."""
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
        if values.get("PUBLIC_IP") != args.public_ip or urlparse(values.get("DATABASE_URL", "")).hostname != args.db_host:
            parser.error("La configuracion AWS existente tiene otro destino; se conserva sin sobrescribir")
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
            "API_LOOPBACK_PORT": "8000", "HTTP_PORT": "80", "HTTPS_PORT": "443",
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
    api_url = "https://{}:{}/api/v1/readings".format(values["PUBLIC_IP"], values["HTTPS_PORT"])
    private_write(secret_dir / "aws-firmware/http.config.h",
                  "#pragma once\n// Configuracion AWS privada: reemplaza API_URL y API_KEY de config.h.\n"
                  + "#undef API_URL\n#undef API_KEY\n"
                  + f"#define API_URL {json.dumps(api_url)}\n"
                  + f"#define API_KEY {json.dumps(values['API_KEY'])}\n"
                  + '#define API_CA_CERT R"RSCA(\n' + ca + ')RSCA"\n')
    print("AWS preparado: claves no impresas; se conserva intacta la configuracion LAN.")
    print("Archivo privado de acceso web: deploy/aws-app/.env (DASHBOARD_USERNAME / DASHBOARD_PASSWORD).")
    print("Firmware TLS: .secrets/aws-firmware/http.config.h; DEVICE_CODE debe ser " + args.device)
    print("Antes de iniciar la aplicacion: solicitar e instalar el certificado con scripts/aws_certificate.py.")


if __name__ == "__main__":
    main()
