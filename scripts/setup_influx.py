"""Add InfluxDB settings to a private .env; keeps existing values and prints no secrets."""
import argparse
import getpass
from pathlib import Path
import secrets
from aws_common import append_env, read_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--url", default="http://influxdb:8086")
    parser.add_argument("--local", action="store_true", help="Compose local: genera clave y token del contenedor")
    args = parser.parse_args()
    if not args.env_file.exists():
        parser.error(f"No existe {args.env_file}; crearlo primero con setup_env.py o setup_aws_app.py")
    current = read_env(args.env_file)
    if current.get("INFLUX_URL") not in (None, args.url):
        parser.error("El archivo ya apunta a otro InfluxDB; se conserva sin sobrescribir")
    if current.get("INFLUX_TOKEN"):
        print("Se conserva la configuracion InfluxDB existente.")
        return
    new = {"INFLUX_URL": args.url}
    if args.local:
        new |= {"INFLUX_TOKEN": secrets.token_hex(32), "INFLUX_ADMIN_PASSWORD": secrets.token_hex(24)}
    else:
        token = getpass.getpass("Token de escritura de InfluxDB (no se muestra): ").strip()
        if not token or "\n" in token or "\r" in token:
            parser.error("El token debe ser una sola linea no vacia")
        new["INFLUX_TOKEN"] = token
    append_env(args.env_file, new)
    print(f"InfluxDB agregado a {args.env_file}; claves no impresas.")


if __name__ == "__main__":
    main()
