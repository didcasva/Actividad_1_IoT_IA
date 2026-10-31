from app.services.influx_store import backfill, enabled

if not enabled():
    raise SystemExit("InfluxDB no configurado: definir INFLUX_URL e INFLUX_TOKEN")
print(f"InfluxDB reconstruido desde la base de datos: {backfill()} mediciones")
