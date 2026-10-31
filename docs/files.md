# Archivos del proyecto

Inventario de fuentes y documentación. El PDF original se conserva; `.env`, `config.h`, `http.config.h`, `.secrets/` y `.backups/` están excluidos de Git.

```text
.dockerignore
.env.example
.gitignore
Actividad 1 2026-2.pdf
README.md
backend/Dockerfile
backend/alembic.ini
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/001_initial.py
backend/alembic/versions/002_demo_dht11.py
backend/app/api/routes.py
backend/app/core/config.py
backend/app/core/database.py
backend/app/main.py
backend/app/models/entities.py
backend/app/repositories/readings.py
backend/app/schemas/readings.py
backend/app/services/csv_store.py
backend/app/services/ingestion.py
backend/requirements.txt
backend/tests/conftest.py
backend/tests/test_api.py
compose.yaml
deploy/aws-app/.env.example
deploy/aws-app/Caddy.acme
deploy/aws-app/Caddyfile
deploy/aws-app/README.md
deploy/aws-app/compose.yaml
deploy/aws-db/.env.example
deploy/aws-db/README.md
deploy/aws-db/compose.yaml
deploy/aws-db/init-app.sql
docs/architecture.md
docs/cloud-migration.md
docs/comunicacion-y-csv.md
docs/database.md
docs/docker-recovery.md
docs/files.md
docs/hardware.md
docs/local-deployment.md
docs/modelo-datos-y-problematica.md
docs/real-device.md
docs/ubuntu-virtualbox.md
docs/validation.md
docs/wifi-troubleshooting.md
firmware/esp32_dht_monitor/BoundedDHT.h
firmware/esp32_dht_monitor/config.example.h
firmware/esp32_dht_monitor/esp32_dht_monitor.ino
frontend/static/Chart.LICENSE.md
frontend/static/app.js
frontend/static/chart.umd.min.js
frontend/static/style.css
frontend/templates/index.html
scripts/aws_certificate.py
scripts/aws_common.py
scripts/reconcile_csv.py
scripts/register_device.py
scripts/setup_aws_app.py
scripts/setup_env.py
scripts/simulate.py
scripts/verify_csv.py
scripts/verify_device.py
```

Total: 63 archivos de fuentes y documentación.
