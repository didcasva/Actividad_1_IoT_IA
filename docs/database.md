# Datos y consistencia

Device: id, device_code único, name, sensor_type (DHT11/DHT22), location, created_at, is_active. Se crea `esp32-01`, Unidad móvil 01, con Alembic; la migración 002 configura DHT11 según el hardware disponible.

SensorReading: id, device_id (FK), temperature_c, humidity_percent, measured_at, received_at, boot_id, sequence_number. Índice (device_id, measured_at), restricción única (device_id, boot_id, sequence_number). Humedad 0–100; temperatura DHT22 −40–80 °C y DHT11 0–50 °C (regla del servicio). Secuencia no negativa. Los límites validan el sensor, no condiciones clínicas.

Fechas PostgreSQL TIMESTAMPTZ en UTC. Se requiere zona horaria en measured_at. Si llega null por ausencia de NTP, measured_at toma el instante de recepción; no representa la hora histórica de una muestra sin reloj. received_at siempre lo fija el servidor. No deducir hora histórica en esa situación.

Reintentar una identidad devuelve la fila original, sin reemplazar valores ni fechas. Cambiar el contenido con la misma identidad no crea una medición nueva.

```sh
docker compose exec db psql -U monitor -d monitor -c "SELECT id,device_id,temperature_c,humidity_percent,measured_at FROM sensor_readings ORDER BY id DESC LIMIT 10;"
docker compose exec api python scripts/verify_csv.py
docker compose exec api python scripts/reconcile_csv.py
docker compose exec api cat /data/readings.csv
```

Ejecutar comparación sin escrituras simultáneas; de lo contrario una nueva fila entre snapshots puede producir una diferencia transitoria. Detener simulador y ESP32 antes de comparar.

Alta de una segunda unidad (desde terminal, cambiar código también en config.h):

```sh
docker compose exec db psql -U monitor -d monitor -c "INSERT INTO devices (device_code,name,sensor_type,location,created_at,is_active) VALUES ('esp32-02','Unidad móvil 02','DHT22','Área de atención',CURRENT_TIMESTAMP,true);"
```
