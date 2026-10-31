# Ruta Salud · Monitoreo ambiental IoT

**Actividades 1 y 2 · IoT e Inteligencia Artificial**

## Integrantes

| Nombre completo | Código universitario |
| --- | --- |
| Didier Manuel Castro Vasquez | 22606316 |
| Ingrid Valentina Sánchez Manzano | 22610485 |
| Jesús Bolaños Botina | 22602601 |
| Daniel Caicedo Villegas | 22601469 |

## Proyecto

Prototipo académico para medir temperatura y humedad en **unidades móviles de salud**, con ESP32 físico y DHT11 (DHT22 configurable). No procesa datos de pacientes ni constituye un sistema clínico certificado.

Arquitectura MQTT: DHT11 → ESP32 → Wi-Fi/hotspot → Mosquitto → receptor Python → PostgreSQL + CSV físico + InfluxDB (opcional). También se conserva el transporte HTTP JSON con X-API-Key hacia FastAPI. Dashboard HTML/CSS/JS con Chart.js y polling cada cinco segundos. Objetivos: integración de sensores, mensajería por topics, API REST, integridad de datos, persistencia y preparación de infraestructura portable.

## Estado actual

- Captura física de temperatura y humedad verificada con ESP32-S3, DHT11 y dispositivo `UM1`.
- Recepción HTTP, almacenamiento en PostgreSQL y CSV, y visualización en el dashboard comprobados.
- Dashboard con selección de unidad, filtros de fecha, gráficas, exportación CSV y aviso tras más de 30 segundos sin recepción.
- Servicios Docker Compose: base de datos, migraciones y API; el perfil `mqtt` agrega Mosquitto y receptor Python. Datos y sesiones del broker conservados en volúmenes persistentes.
- MQTT con usuarios/ACL por topic, publicaciones QoS 1, acuse de guardado PostgreSQL/CSV e idempotencia compartida con HTTP. Ver [configuración y pruebas MQTT](docs/mqtt.md).
- Suite de 29 pruebas backend aprobada con PostgreSQL en una base de pruebas independiente. Ingestión MQTT y permisos comprobados con mensajes sintéticos en un despliegue aislado.
- Firmware MQTT compilado y cargado en la ESP32-S3 física por COM4. Captura real de UM1 por MQTT y acuses de guardado PostgreSQL/CSV verificados; las pruebas HTTP anteriores también se conservan como evidencia.
- Guía de instalación en Ubuntu Server con Oracle VirtualBox disponible; la ejecución y validación en esa VM están pendientes.
- AWS: aplicación pública desplegada en `3.231.16.96`, PostgreSQL en EC2 privada, dashboard HTTPS con contraseña y broker MQTT TLS en 8883. ESP32-S3 cargado y captura física de UM1 confirmada en AWS, con acuses de guardado y coincidencia PostgreSQL/CSV. Temporizador de certificados activo y primera ejecución automática correcta.
- InfluxDB 2.7.12 desplegado en la EC2 privada y comprobado con el ESP32 físico. Primer corte: 2.951 mediciones coincidentes en PostgreSQL/CSV/InfluxDB. Tras la prueba de recuperación: 3.186 coincidentes entre PostgreSQL e InfluxDB, sin puntos adicionales. Los conteos pertenecen a momentos distintos. Ver [evidencias de AWS](docs/validation.md#actividad-2-en-aws).
- Grafana 13.2.5 disponible por HTTPS en `/grafana/`, con dashboard y tres reglas aprovisionadas. Se confirmó el disparo de la alerta de falta de datos, un aviso real en Discord, la recuperación a `Normal` y el mensaje `Resolved`. Discord es un complemento opcional de la implementación. Ver [Grafana](docs/grafana.md).
- Docker y containerd habilitados al inicio en ambas EC2; siete servicios permanentes con `unless-stopped`, swap persistente de 1 GiB en cada servidor y temporizador TLS habilitado y activo en la pública. La raíz pública se amplió sobre un EBS de 15 GiB. Falta confirmar el arranque mediante un reinicio completo de ambas EC2.
- La revisión local de la actividad 2 aprobó 40 pruebas con SQLite temporal y validó ambos Compose de AWS con valores ficticios. Las pruebas remotas guiadas y sus límites se registran por separado en la [bitácora](docs/bitacora-aws-actividad2.md).

Los ensayos y sus límites están registrados en [validación](docs/validation.md), [captura física](docs/real-device.md) y [recuperación de Docker](docs/docker-recovery.md). La recuperación controlada tras interrupciones de Wi-Fi, la estabilidad prolongada y las pruebas en vehículo siguen pendientes.

## Instalación en AWS: dos EC2

Seguir la [guía de aplicación pública HTTPS y MQTT TLS](deploy/aws-app/README.md) para la IP elástica `3.231.16.96` y la [guía de PostgreSQL privado](deploy/aws-db/README.md) para `192.168.1.142`. La aplicación se conecta a la base por la VPC. El dashboard requiere contraseña; el broker público usa 8883 con TLS y ACL por dispositivo. Los certificados por IP se renuevan automáticamente mediante systemd.

Usar `deploy/aws-app/compose.yaml` con su propio `.env` generado por `scripts/setup_aws_app.py`. El Compose raíz sigue destinado a la LAN. No copiar credenciales locales al repositorio ni iniciar otra BD en el servidor público. La guía incluye emisión del certificado, migraciones, registro de UM1 y cambio del ESP32 a la nube.

## Instalación en Ubuntu Server / VirtualBox

Seguir la [guía completa de instalación](docs/ubuntu-virtualbox.md): configuración de red puente, Docker Engine y Compose, secretos locales, registro de `UM1`, configuración del ESP32 y comprobación de mediciones reales.

Con Git instalado en Ubuntu, descargar el proyecto:

```bash
git clone https://github.com/didcasva/Actividad_1_IoT_IA.git
cd Actividad_1_IoT_IA
```

Desde Windows o desde el ESP32 se accede mediante la **IP LAN de Ubuntu**. `localhost` en Windows apunta a Windows. El repositorio contiene las fuentes; no incluye credenciales ni el histórico de mediciones de otra instalación.

## Inicio rápido — PowerShell

Para MQTT seguir [la guía de activación](docs/mqtt.md). Con Docker activo y `.env` creado:

```powershell
python scripts/setup_mqtt.py --host IP_LAN_DEL_SERVIDOR --device UM1
docker compose --profile mqtt up -d --build
```

El script conserva claves HTTP/BD y genera credenciales MQTT privadas y `mqtt.config.h`. Instalar **MQTT by Joel Gaehwiler** en Arduino IDE y cargar el sketch para activar MQTT. Registrar UM1 como se indica abajo si la base es nueva. En Ubuntu usar `python3`; la [guía MQTT](docs/mqtt.md) explica `--sudo-docker` y la transferencia del archivo privado al PC de programación.

Para ejecutar únicamente los servicios HTTP anteriores:

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
  tests/{conftest.py,test_api.py,test_mqtt.py,test_influx.py}
  alembic.ini, requirements.txt, Dockerfile
frontend/{templates/index.html,static/app.js,static/style.css}
firmware/esp32_dht_monitor/{esp32_dht_monitor.ino,BoundedDHT.h,config.example.h}
firmware/esp32_dht_monitor/mqtt.config.example.h
mqtt/mosquitto.conf
grafana/provisioning/{datasources,dashboards,alerting}/
backend/app/mqtt_worker.py, backend/app/services/mqtt_ingestion.py
scripts/{setup_env.py,setup_mqtt.py,simulate.py,reconcile_csv.py,verify_csv.py,verify_device.py,verify_mqtt.py}
scripts/{aws_common.py,setup_aws_app.py,aws_certificate.py,register_device.py}
scripts/{setup_influx.py,reconcile_influx.py,verify_influx.py,setup_grafana.py}
deploy/{aws-db,aws-app}/
docs/{architecture,database,hardware,local-deployment,ubuntu-virtualbox}.md
docs/{mqtt,real-device,wifi-troubleshooting,docker-recovery,cloud-migration,validation,files}.md
docs/{grafana,comunicacion-y-csv,modelo-datos-y-problematica}.md
docs/{guia-presentacion-actividad2,bitacora-aws-actividad2}.md
compose.yaml, .env.example, .gitignore, .dockerignore
```

Guías: [arquitectura](docs/architecture.md), [datos y verificación CSV](docs/database.md), [conexión ESP32 físico](docs/hardware.md), [diagnóstico Wi-Fi y reinicios](docs/wifi-troubleshooting.md), [Windows y Ubuntu local/VM](docs/local-deployment.md), [fase de nube, backups y seguridad](docs/cloud-migration.md), [resultados reales](docs/validation.md).

Para presentar y entregar: [guion de exposición de la actividad 2](docs/guia-presentacion-actividad2.md) y [bitácora técnica: qué se hizo, cómo y qué falta comprobar](docs/bitacora-aws-actividad2.md).

Apoyo para la exposición: [problemática, arquitectura AWS y modelo de datos](docs/modelo-datos-y-problematica.md), [datos del ESP32, métodos HTTP/MQTT y consulta del CSV por SSH](docs/comunicacion-y-csv.md). La consigna original de la actividad 2 no está en el repositorio; la documentación describe la implementación y las pruebas disponibles.

Repositorio: https://github.com/didcasva/Actividad_1_IoT_IA.git. La configuración real se mantiene en `.env`, `config.h`, `mqtt.config.h` y `.secrets/`, excluidos de Git y de las imágenes.

Docker Compose utiliza el proyecto taller1 y las imágenes actividad1-iot-ia-api:local / actividad1-iot-ia-migrate:local / actividad1-iot-ia-mqtt:local; el broker usa eclipse-mosquitto:2.0. Ver [recuperación de Docker y comprobación de datos](docs/docker-recovery.md) si falla la red interna o una referencia de imagen. Los respaldos locales .backups/ están excluidos de Git y de las imágenes.
