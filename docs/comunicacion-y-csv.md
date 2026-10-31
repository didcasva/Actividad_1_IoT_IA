# Ruta Salud: comunicación del ESP32 y archivo CSV

Guía de apoyo para explicar los datos transmitidos, los métodos HTTP y la consulta del CSV por SSH. Describe la implementación del proyecto al 30 de octubre de 2026.

## Datos que envía el ESP32

El firmware toma una muestra de temperatura ambiental y humedad del DHT11 cada 10 segundos. Valida la lectura y la guarda en una cola persistente antes de intentar enviarla. El mensaje utiliza JSON; estos valores son de ejemplo:

```json
{
  "device_code": "UM1",
  "temperature_c": 26.5,
  "humidity_percent": 68.0,
  "boot_id": "a3f91c2b7d6840e1b5a690c8d24f7310",
  "sequence_number": 42,
  "measured_at": "2026-10-30T15:30:00Z"
}
```

| Campo enviado | Significado |
| --- | --- |
| `device_code` | Código del dispositivo asignado a la unidad, por ejemplo `UM1`. |
| `temperature_c` | Temperatura ambiental en grados Celsius. |
| `humidity_percent` | Humedad relativa en porcentaje. |
| `boot_id` | Identificador aleatorio generado en cada arranque del ESP32. |
| `sequence_number` | Contador de muestras dentro de ese arranque, desde cero. |
| `measured_at` | Instante de la medición en UTC, con formato ISO 8601. |

Cuando el dispositivo todavía no tiene hora sincronizada mediante NTP, envía `measured_at: null`. El servidor asigna entonces la hora de recepción; ese valor no reconstruye la hora original de una muestra que estuvo en cola sin reloj.

El servidor agrega `id`, `device_id` y `received_at`. `device_id` es la referencia interna al dispositivo registrado y se obtiene a partir de `device_code`. Por eso el CSV contiene campos que no aparecen en el mensaje del ESP32.

La combinación única `(device_id, boot_id, sequence_number)` permite reconocer un reintento y devolver la medición original sin insertar otra fila. El firmware conserva hasta 60 muestras en NVS; si la cola se llena, descarta las muestras nuevas e informa por Serial.

## Métodos HTTP de la API

La API utiliza `POST` para recibir mediciones y `GET` para consultas y exportación.

| Método | Ruta | Uso |
| --- | --- | --- |
| `POST` | `/api/v1/readings` | Recibir el JSON de una medición. Requiere la cabecera `X-API-Key`. |
| `GET` | `/api/v1/readings` | Consultar el histórico con filtros y paginación. |
| `GET` | `/api/v1/readings/latest` | Consultar la última medición según los filtros. |
| `GET` | `/api/v1/devices` | Listar los dispositivos registrados. |
| `GET` | `/api/v1/readings/export.csv` | Descargar un CSV de las mediciones filtradas. |
| `GET` | `/health` | Comprobar SQL y reconstrucción del CSV. |

Las consultas de mediciones admiten `device_id`, `start` y `end`. Las fechas deben incluir zona horaria. El histórico admite además `limit` y `offset`. La exportación incluye todas las filas que cumplen los filtros, sin la paginación del histórico.

El dashboard consulta la API cada cinco segundos. En AWS, Caddy proporciona HTTPS y autenticación para el dashboard y sus consultas; la ingestión HTTP utiliza `X-API-Key`. El firmware usa HTTPS con validación de certificado hacia AWS cuando existe `http.config.h`; sin ese archivo usa HTTP en la LAN.

## Envío por HTTPS

En el despliegue AWS, el ESP32 envía cada muestra con `POST https://IP:443/api/v1/readings`, valida el certificado del servidor e incluye la cabecera `X-API-Key`. Caddy recibe la conexión y la reenvía a FastAPI, que valida el JSON y guarda la medición en PostgreSQL y en el CSV.

El ESP32 mantiene cada muestra en NVS hasta recibir una respuesta 2xx. Si no la recibe, reintenta con la misma identidad, y la base de datos evita duplicarla. El dashboard obtiene las mediciones mediante HTTP y su indicador de recepción utiliza `received_at`.

## Cómo se implementó el CSV

PostgreSQL es la fuente de los registros. El servicio `csv_store.py` genera el archivo con el módulo estándar `csv` de Python, siguiendo este orden:

1. El servicio de ingestión confirma primero la medición en PostgreSQL.
2. `reconcile()` toma un bloqueo `FileLock`, compartido entre procesos mediante un archivo `.lock`.
3. Consulta todas las mediciones ordenadas por `id` y escribe encabezados y filas en un archivo temporal, en la misma carpeta del CSV.
4. Ejecuta `flush()` y `os.fsync()` antes de cerrar el temporal.
5. Reemplaza el CSV anterior con `os.replace()`, para que los lectores vean un archivo completo.

Las columnas del archivo son:

```csv
id,device_id,temperature_c,humidity_percent,measured_at,received_at,boot_id,sequence_number
```

Las fechas se serializan en formato ISO 8601. Si falla la escritura del CSV, la medición ya confirmada permanece en PostgreSQL. HTTP devuelve `503` para que el dispositivo reintente la misma identidad. La API intenta reconciliar el archivo al iniciar y cada 30 segundos, y también al consultar `/health`.

La base de datos y el archivo no forman una transacción conjunta: una interrupción puede dejar el CSV temporalmente atrasado. La reconstrucción permite recuperarlo desde PostgreSQL. Actualmente se reconstruye todo el histórico con cada recepción, por lo que el costo aumenta al crecer los registros.

El botón de exportación del dashboard llama a `GET /api/v1/readings/export.csv`. Esa ruta genera en memoria un CSV desde PostgreSQL con los filtros seleccionados; no descarga directamente el archivo persistente completo.

## Ver el CSV desde SSH en AWS

El CSV queda en la **EC2 pública de la aplicación**, configurada con IP elástica `3.231.16.96`. PostgreSQL queda en la EC2 privada. Dentro del contenedor `api`, la ruta del CSV es `/data/readings.csv`, respaldada por el volumen `rutasalud-app_csv_data`.

Después de entrar por SSH a la instancia pública, ir al repositorio y consultar las últimas diez mediciones:

```bash
cd ~/Actividad_1_IoT_IA
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml exec -T api tail -n 10 /data/readings.csv
```

Para ver el encabezado y las primeras filas:

```bash
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml exec -T api head -n 10 /data/readings.csv
```

Para seguir las nuevas mediciones mientras el servicio reemplaza el archivo, utilizar `-F`, que sigue el nombre del archivo. Salir con `Ctrl+C`:

```bash
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml exec -T api tail -n 10 -F /data/readings.csv
```

La carpeta del volumen en el servidor normalmente es `/var/lib/docker/volumes/rutasalud-app_csv_data/_data`. Confirmar la ubicación real, que depende de la configuración de Docker, con:

```bash
sudo docker volume inspect rutasalud-app_csv_data --format '{{ .Mountpoint }}'
```

Para verificar que el CSV coincide con PostgreSQL:

```bash
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml exec -T api python scripts/verify_csv.py
```

La comparación debe realizarse sin nuevas escrituras simultáneas, porque una medición recibida entre las dos consultas puede producir una diferencia transitoria. Más detalles en [datos y consistencia](database.md).

## Archivos de referencia

- [Firmware ESP32](../firmware/esp32_dht_monitor/esp32_dht_monitor.ino).
- [Contrato del JSON](../backend/app/schemas/readings.py).
- [Rutas HTTP](../backend/app/api/routes.py).
- [Servicio de ingestión](../backend/app/services/ingestion.py).
- [Generación del CSV](../backend/app/services/csv_store.py).
- [Reconciliación periódica](../backend/app/main.py).
- [Compose de AWS](../deploy/aws-app/compose.yaml).
- [Problemática, arquitectura AWS y modelo de datos](modelo-datos-y-problematica.md).
