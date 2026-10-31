"""Helpers for the separate AWS deployment; never read or replace the LAN .env."""
from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
AWS_DIR = ROOT / "deploy/aws-app"
ENV_FILE = AWS_DIR / ".env"


def read_env(path=ENV_FILE):
    values = {}
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    return values


def private_write(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(body)
    path.chmod(0o600)


def append_env(path, values):
    path = Path(path)
    body = path.read_text(encoding="utf-8-sig")
    separator = "" if not body or body.endswith("\n") else "\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(separator + "".join(f"{key}={value}\n" for key, value in values.items()))


def docker_command(sudo=False):
    return ["sudo", "docker"] if sudo else ["docker"]


def compose(sudo=False):
    return docker_command(sudo) + ["compose", "--env-file", str(ENV_FILE), "-f", str(AWS_DIR / "compose.yaml")]


def run(arguments, **kwargs):
    return subprocess.run(arguments, check=True, **kwargs)
