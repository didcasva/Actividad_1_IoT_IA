from app.services.influx_store import enabled, expected, stored

if not enabled():
    raise SystemExit("InfluxDB no configurado: definir INFLUX_URL e INFLUX_TOKEN")
sql, influx = expected(), stored()
missing = sql.keys() - influx.keys()
different = [key for key in sql.keys() & influx.keys() if sql[key] != influx[key]]
assert not missing and not different, (
    f"InfluxDB diferente de la base de datos: {len(missing)} faltantes, {len(different)} distintas; ejecute reconciliación")
print(f"Coincidencia exacta: {len(sql)} mediciones ({len(influx) - len(sql)} puntos adicionales en InfluxDB)")
