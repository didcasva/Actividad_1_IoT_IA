"""Issue/renew an IP certificate and atomically activate it for Caddy and Mosquitto."""
import argparse
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import time
from aws_common import ROOT, compose, read_env, run


def sync_certificate(public_ip):
    if os.name != "posix" or os.geteuid() != 0:
        raise SystemExit("La activacion del certificado requiere sudo en el servidor Linux")
    source = ROOT / ".secrets/aws-letsencrypt/live/rutasalud-ip"
    cert, key = source / "fullchain.pem", source / "privkey.pem"
    run(["openssl", "verify", "-CAfile", str(ROOT / ".secrets/aws-ca.pem"),
         "-untrusted", str(cert), "-verify_ip", public_ip, str(cert)], capture_output=True)
    run(["openssl", "x509", "-in", str(cert), "-noout", "-checkend", "3600"], capture_output=True)
    certificate_key = run(["openssl", "x509", "-in", str(cert), "-pubkey", "-noout"], capture_output=True).stdout
    private_key = run(["openssl", "pkey", "-in", str(key), "-pubout"], capture_output=True).stdout
    if certificate_key != private_key:
        raise SystemExit("Certificado y clave privada no coinciden; no se activa")
    digest = hashlib.sha256(cert.read_bytes() + key.read_bytes()).hexdigest()
    target = ROOT / ".secrets/aws-tls"
    current = target / "current"
    if current.exists() and (current / "fingerprint").read_text() == digest:
        return False
    target.mkdir(exist_ok=True)
    target.chmod(0o755)
    generation = target / (str(time.time_ns()) + "-" + digest[:12])
    generation.mkdir(mode=0o750)
    os.chown(generation, 0, 1883)
    for name in ("fullchain.pem", "privkey.pem"):
        output = generation / name
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(fd, "wb") as stream:
            stream.write((source / name).read_bytes())
        os.chown(output, 0, 1883)
    (generation / "fingerprint").write_text(digest)
    temporary = target / "current.new"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(generation.name, target_is_directory=True)
    temporary.replace(current)  # El par certificado/clave cambia de forma atomica.
    return True


def install_timer():
    if os.name != "posix" or os.geteuid() != 0:
        raise SystemExit("Instalar el timer requiere sudo en Ubuntu")
    # Restriccion para no introducir directivas inesperadas en systemd.
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(ROOT)):
        raise SystemExit("Instalar el proyecto en una ruta Linux sin espacios ni caracteres especiales")
    service = f"""[Unit]
Description=Renovar certificado IP de Ruta Salud y recargar TLS
Wants=network-online.target docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
WorkingDirectory={ROOT}
ExecStart=/usr/bin/python3 {ROOT}/scripts/aws_certificate.py renew
"""
    timer = """[Unit]
Description=Revision de certificado Ruta Salud cada 12 horas

[Timer]
OnBootSec=10min
OnCalendar=*-*-* 00,12:00:00
RandomizedDelaySec=15min
Persistent=true

[Install]
WantedBy=timers.target
"""
    Path("/etc/systemd/system/rutasalud-cert-renew.service").write_text(service)
    Path("/etc/systemd/system/rutasalud-cert-renew.timer").write_text(timer)
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "rutasalud-cert-renew.timer"])
    print("Timer instalado. Revisar systemctl list-timers rutasalud-cert-renew.timer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["issue", "sync", "renew", "install-timer", "dry-run"])
    parser.add_argument("--sudo-docker", action="store_true")
    parser.add_argument("--email", help="Correo opcional para avisos de la cuenta ACME")
    parser.add_argument("--no-reload", action="store_true", help="Solo sync: preparar archivos antes del primer arranque")
    args = parser.parse_args()
    if args.no_reload and args.action != "sync":
        parser.error("--no-reload solo se admite con sync")
    values = read_env()
    ip = str(ipaddress.IPv4Address(values["PUBLIC_IP"]))
    command = compose(args.sudo_docker)
    if args.action == "install-timer":
        install_timer()
        return
    if args.action == "issue":
        if not ipaddress.ip_address(ip).is_global:
            parser.error("La emision ACME requiere una IP publica enrutable")
        run(command + ["--profile", "bootstrap", "up", "-d", "acme-web"])
        account = ["--email", args.email] if args.email else ["--register-unsafely-without-email"]
        run(command + ["run", "--rm", "certbot", "certonly", "--non-interactive", "--agree-tos",
                       "--preferred-profile", "shortlived", "--webroot", "-w", "/var/www/certbot",
                       "--cert-name", "rutasalud-ip", "--ip-address", ip, "--key-type", "rsa"] + account)
        print("Certificado obtenido. Ejecutar sudo python3 scripts/aws_certificate.py sync")
        return
    if args.action in ("renew", "dry-run"):
        run(command + ["run", "--rm", "certbot", "renew", "--quiet"] + (["--dry-run"] if args.action == "dry-run" else []))
        if args.action == "dry-run":
            return
    changed = sync_certificate(ip)
    if args.no_reload:
        print("Par TLS preparado." if changed else "Par TLS vigente.")
        return
    # Recargar incluso si el certificado ya fue copiado: recupera un reload fallido previo.
    for service in ("caddy", "broker"):
        running = run(command + ["ps", "--status", "running", "-q", service], text=True, capture_output=True).stdout.strip()
        if running:
            if service == "caddy":
                run(command + ["exec", "-T", service, "caddy", "reload", "--force", "--config", "/etc/caddy/Caddyfile"])
            else:
                run(command + ["kill", "-s", "HUP", service])
    print("Par TLS actualizado y recargado." if changed else "Certificado vigente; recargas comprobadas.")


if __name__ == "__main__":
    main()
