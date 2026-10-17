# Ruta Salud · Monitoreo ambiental IoT

Prototipo académico para medir temperatura y humedad en **unidades móviles de salud**, con ESP32 físico y DHT11 (DHT22 configurable). No procesa datos de pacientes ni constituye un sistema clínico certificado.

Arquitectura: DHT11 → ESP32 → Wi-Fi/hotspot → HTTP JSON con X-API-Key → FastAPI → PostgreSQL + CSV físico. Dashboard HTML/CSS/JS con Chart.js y polling cada cinco segundos. Objetivos: integración de sensores, API REST, integridad de datos, persistencia y preparación de infraestructura portable.

## Inicio rápido — PowerShell

Desde esta carpeta, con Python y Docker Desktop Linux iniciados:

```powershell
python scripts/setup_env.py
docker compose up -d --build
Invoke-RestMethod http://localhost:8000/health
$env:API_KEY = (Get-Content .env | Where-Object { $_ -like 'API_KEY=*' }) -replace '^API_KEY=', ''
python scripts/simulate.py --count 10 --interval 1
docker compose exec api python scripts/verify_csv.py
```

Dashboard: http://localhost:8000 · OpenAPI: http://localhost:8000/docs. Desde otro equipo usar la IP LAN. Las migraciones Alembic se ejecutan antes del servicio API. .env.example explica las variables; setup_env genera secretos sin sobrescribir .env. Si edita la contraseña manualmente debe coincidir en POSTGRES_PASSWORD y DATABASE_URL (codificar caracteres especiales en URL).

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
docker compose run --rm api python -c "import os; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL'].rsplit('/',1)[0]+'/monitor_test'; import pytest; raise SystemExit(pytest.main(['backend/tests','-q','-p','no:cacheprovider']))"
```

## Estructura

```text
backend/
  app/{api,core,models,schemas,repositories,services}/
  app/main.py
  alembic/{env.py,script.py.mako,versions/001_initial.py,versions/002_demo_dht11.py}
  tests/{conftest.py,test_api.py}
  alembic.ini, requirements.txt, Dockerfile
frontend/{templates/index.html,static/app.js,static/style.css}
firmware/esp32_dht_monitor/{esp32_dht_monitor.ino,config.example.h}
scripts/{setup_env.py,simulate.py,reconcile_csv.py,verify_csv.py}
docs/{architecture,database,hardware,local-deployment,cloud-migration,validation}.md
compose.yaml, .env.example, .gitignore, .dockerignore
```

Guías: [arquitectura](docs/architecture.md), [datos y verificación CSV](docs/database.md), [conexión ESP32 físico](docs/hardware.md), [Windows y Ubuntu local/VM](docs/local-deployment.md), [fase de nube, backups y seguridad](docs/cloud-migration.md), [resultados reales](docs/validation.md).

Repositorio: https://github.com/didcasva/Actividad_1_IoT_IA.git. La configuración real de red y credenciales se mantiene exclusivamente en .env y config.h, excluidos de Git.
