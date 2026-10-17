"""Create local secrets without overwriting existing configuration."""
import secrets
from pathlib import Path

target = Path(".env")
if target.exists():
    raise SystemExit(".env ya existe; se conserva sin cambios")
password = secrets.token_hex(24)
target.write_text(f"POSTGRES_PASSWORD={password}\nDATABASE_URL=postgresql+psycopg://monitor:{password}@db:5432/monitor\nAPI_KEY={secrets.token_hex(32)}\nCSV_PATH=/data/readings.csv\nAPI_PORT=8000\n", encoding="utf-8")
print(".env creado con secretos aleatorios. No compartir ni agregar a Git.")
