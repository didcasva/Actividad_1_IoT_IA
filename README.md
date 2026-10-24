# Ruta Salud · Monitoreo ambiental IoT

**Actividad 1 · IoT e Inteligencia Artificial**

## Integrantes

| Nombre completo | Código universitario |
| --- | --- |
| Didier Manuel Castro Vasquez | 22606316 |
| Ingrid Valentina Sánchez Manzano | 22610485 |

## Proyecto

Prototipo académico para medir temperatura y humedad en **unidades móviles de salud**, con ESP32 físico y DHT11 (DHT22 configurable). No procesa datos de pacientes ni constituye un sistema clínico certificado.

Arquitectura: DHT11 → ESP32 → Wi-Fi/hotspot → HTTP JSON con X-API-Key → FastAPI → PostgreSQL + CSV físico. Dashboard HTML/CSS/JS con Chart.js y polling cada cinco segundos. Objetivos: integración de sensores, API REST, integridad de datos, persistencia y preparación de infraestructura portable.

## Estado actual

- Captura física de temperatura y humedad verificada con ESP32-S3, DHT11 y dispositivo `UM1`.
- Recepción HTTP, almacenamiento en PostgreSQL y CSV, y visualización en el dashboard comprobados.
- Dashboard con selección de unidad, filtros de fecha, gráficas, exportación CSV y aviso tras más de 30 segundos sin recepción.
- Servicios Docker Compose: base de datos, migraciones y API. Datos conservados en volúmenes persistentes.
- Suite de 15 pruebas backend aprobada con PostgreSQL en una base de pruebas independiente.
- Guía de instalación en Ubuntu Server con Oracle VirtualBox disponible; la ejecución y validación en esa VM están pendientes.

Los ensayos y sus límites están registrados en [validación](docs/validation.md), [captura física](docs/real-device.md) y [recuperación de Docker](docs/docker-recovery.md). La recuperación controlada tras interrupciones de Wi-Fi, la estabilidad prolongada y las pruebas en vehículo siguen pendientes. El despliegue en nube corresponde a una fase posterior.

## Instalación en Ubuntu Server / VirtualBox

Seguir la [guía completa de instalación](docs/ubuntu-virtualbox.md): configuración de red puente, Docker Engine y Compose, secretos locales, registro de `UM1`, configuración del ESP32 y comprobación de mediciones reales.

Con Git instalado en Ubuntu, descargar el proyecto:

```bash
git clone https://github.com/didcasva/Actividad_1_IoT_IA.git
cd Actividad_1_IoT_IA
```

Desde Windows o desde el ESP32 se accede mediante la **IP LAN de Ubuntu**. `localhost` en Windows apunta a Windows. El repositorio contiene las fuentes; no incluye credenciales ni el histórico de mediciones de otra instalación.

## Inicio rápido — PowerShell

Desde esta carpeta, con Python y Docker Desktop Linux iniciados:

```powershell
python scripts/setup_env.py
docker compose up -d --build
Invoke-RestMethod http://localhost:8000/health
```

Dashboard: http://localhost:8000 · OpenAPI: http://localhost:8000/docs. Desde otro equipo usar la IP LAN. Las migraciones Alembic se ejecutan antes del servicio API. .env.example explica las variables; setup_env genera secretos sin sobrescribir .env. Si edita la contraseña manualmente debe coincidir en POSTGRES_PASSWORD y DATABASE_URL (codificar caracteres especiales en URL).

En una instalación nueva, registrar la unidad física `UM1` después de arrancar los servicios:

```powershell
docker compose exec db psql -U monitor -d monitor -c "INSERT INTO devices (device_code,name,sensor_type,location,created_at,is_active) VALUES ('UM1','Unidad movil de salud UM1','DHT11','Area de atencion',CURRENT_TIMESTAMP,true) ON CONFLICT (device_code) DO NOTHING;"
```

Configurar en el archivo privado `firmware/esp32_dht_monitor/config.h` la red Wi-Fi de 2.4 GHz, `DEVICE_CODE` igual a `UM1`, la URL `http://IP_LAN_DEL_SERVIDOR:8000/api/v1/readings` y la misma `API_KEY` del `.env`. Mantener `DHT_PIN` en `4` y `DHT_TYPE` en `DHT11`. Cargar el firmware con Arduino IDE siguiendo [la guía de hardware](docs/hardware.md).

Dispositivo físico: [abrir UM1](http://localhost:8000/?device_code=UM1). El firmware envía las muestras automáticamente; no ejecutar el simulador para verificar el sensor real. Ver [captura y comprobación de nuevas mediciones](docs/real-device.md). El dashboard indica si han pasado más de 30 s sin recepción y permite consultar el histórico conservado.

Comprobar nuevas recepciones y coincidencia entre PostgreSQL y CSV:

```powershell
python scripts/verify_device.py --device UM1 --samples 3 --timeout 45
docker compose exec api python scripts/verify_csv.py
```

### Simulación opcional

Solo para pruebas sin el sensor físico, el dispositivo inicial `esp32-01` permite generar muestras de demostración:

```powershell
$env:API_KEY = (Get-Content .env | Where-Object { $_ -like 'API_KEY=*' }) -replace '^API_KEY=', ''
python scripts/simulate.py --count 10 --interval 1
```

## API REST

Ejemplo JSON para POST /api/v1/readings (encabezados Content-Type: application/json y X-API-Key):

```json
{"device_code":"esp32-01","temperature_c":25.5,"humidity_percent":61,"measured_at":"2026-10-17T15:00:00Z","boot_id":"arranque-001","sequence_number":0}
```

En ausencia de NTP enviar measured_at null. Cada reintento debe preservar boot_id y sequence_number.

API: POST /api/v1/readings; GET /api/v1/readings (device_id, start, end, limit 1–1000, offset); GET /api/v1/readings/latest; GET /api/v1/devices; GET /api/v1/readings/export.csv (mismos filtros); GET /health; GET /docs. Fechas de filtros deben incluir zona, por ejemplo 2026-10-17T00:00:00Z. Errores FastAPI usan JSON detail. Ingestión idempotente responde 200 tanto al insertar como al reintentar.

## Pruebas sin Docker

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
$env:PYTHONPATH='backend'
.venv/Scripts/python -m pytest backend/tests -q
```

En Ubuntu usar `python3 -m venv .venv`, `.venv/bin/python` y `export PYTHONPATH=backend`. La suite usa SQLite temporal por defecto: **no equivale a validar PostgreSQL**. Para probar con PostgreSQL definir TEST_DATABASE_URL hacia una base dedicada y descartable; la fixture vacía sus tablas. Nunca apuntarla a una BD con datos que quiera conservar.

```powershell
docker compose exec db createdb -U monitor monitor_test
docker compose run --rm --no-deps api python -c "import os; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL'].rsplit('/',1)[0]+'/monitor_test'; import pytest; raise SystemExit(pytest.main(['backend/tests','-q','-p','no:cacheprovider']))"
```

Crear `monitor_test` solo la primera vez; si ya existe, ejecutar únicamente el segundo comando.

## Estructura

```text
backend/
  app/{api,core,models,schemas,repositories,services}/
  app/main.py
  alembic/{env.py,script.py.mako,versions/001_initial.py,versions/002_demo_dht11.py}
  tests/{conftest.py,test_api.py}
  alembic.ini, requirements.txt, Dockerfile
frontend/{templates/index.html,static/app.js,static/style.css}
firmware/esp32_dht_monitor/{esp32_dht_monitor.ino,BoundedDHT.h,config.example.h}
scripts/{setup_env.py,simulate.py,reconcile_csv.py,verify_csv.py,verify_device.py}
docs/{architecture,database,hardware,local-deployment,ubuntu-virtualbox}.md
docs/{real-device,wifi-troubleshooting,docker-recovery,cloud-migration,validation,files}.md
compose.yaml, .env.example, .gitignore, .dockerignore
```

Guías: [arquitectura](docs/architecture.md), [datos y verificación CSV](docs/database.md), [conexión ESP32 físico](docs/hardware.md), [diagnóstico Wi-Fi y reinicios](docs/wifi-troubleshooting.md), [Windows y Ubuntu local/VM](docs/local-deployment.md), [fase de nube, backups y seguridad](docs/cloud-migration.md), [resultados reales](docs/validation.md).

Repositorio: https://github.com/didcasva/Actividad_1_IoT_IA.git. La configuración real de red y credenciales se mantiene exclusivamente en .env y config.h, excluidos de Git.

Docker Compose utiliza el proyecto taller1 y las imágenes actividad1-iot-ia-api:local / actividad1-iot-ia-migrate:local. Ver [recuperación de Docker y comprobación de datos](docs/docker-recovery.md) si falla la red interna o una referencia de imagen. Los respaldos locales .backups/ están excluidos de Git y de las imágenes.
