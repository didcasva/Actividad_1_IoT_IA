"""Add Grafana settings to a private .env; keeps existing values and prints no secrets."""
import argparse
import getpass
from pathlib import Path
import secrets
from urllib.parse import urlparse
from aws_common import append_env, read_env


def secret(parser, prompt):
    value = getpass.getpass(prompt).strip()
    if not value or "\n" in value or "\r" in value or "$" in value:
        parser.error("El valor debe ser una sola linea no vacia y sin el caracter $")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--local", action="store_true", help="Compose local: reutiliza INFLUX_TOKEN")
    args = parser.parse_args()
    if not args.env_file.exists():
        parser.error(f"No existe {args.env_file}")
    current = read_env(args.env_file)
    if current.get("GRAFANA_ADMIN_PASSWORD"):
        print("Se conserva la configuracion Grafana existente.")
        return
    if args.local and not current.get("INFLUX_TOKEN"):
        parser.error("Ejecutar primero setup_influx.py --local")
    token = current["INFLUX_TOKEN"] if args.local else secret(parser, "Token de lectura de InfluxDB (no se muestra): ")
    webhook = secret(parser, "URL del webhook de Discord (no se muestra): ")
    if urlparse(webhook).scheme != "https":
        parser.error("El webhook debe usar https")
    append_env(args.env_file, {"GRAFANA_ADMIN_PASSWORD": secrets.token_hex(16), "GRAFANA_INFLUX_TOKEN": token,
                               "GRAFANA_ALERT_WEBHOOK_URL": webhook})
    print(f"Grafana agregado a {args.env_file}; claves no impresas.")


if __name__ == "__main__":
    main()
