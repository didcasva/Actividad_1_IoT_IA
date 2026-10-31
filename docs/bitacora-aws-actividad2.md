# Actividad 2 en AWS: bitácora técnica y operación

**Fecha de corte:** 30 de octubre de 2026, `America/Bogota`. Las marcas UTC del servidor después de las 00:00 del 31 corresponden todavía al día 30 en Colombia.

Este registro reúne las acciones guiadas por chat, las salidas SSH y las capturas aportadas por el usuario. El usuario ejecutó las operaciones remotas. Las verificaciones locales del repositorio se distinguen de las comprobaciones en AWS. No se guardan contraseñas, tokens, claves SSH ni URLs de webhooks en este documento.

Para exponer el proyecto, usar la [guía de presentación](guia-presentacion-actividad2.md). Para las instrucciones iniciales completas, consultar los Compose y las guías de [aplicación pública](../deploy/aws-app/README.md) y [bases privadas](../deploy/aws-db/README.md).

## Resultado y alcance confirmado

El código de la actividad 2 ya estaba integrado en `main` por el PR #1, commit `4973629`. Se descargó localmente y se actualizó la copia de AWS. Se instalaron InfluxDB y Grafana sobre la infraestructura previa, se cargó el histórico de PostgreSQL y se verificó la recepción del ESP32 físico. Se probó la alerta de ausencia de mediciones, su entrega real a Discord y la recuperación posterior.

| Elemento | Resultado |
| --- | --- |
| API, receptor MQTT, broker y Grafana | Contenedores saludables en la pública. |
| PostgreSQL e InfluxDB | Contenedores saludables en la privada. |
| Histórico inicial | 2.951 filas coincidentes entre PostgreSQL, CSV e InfluxDB. |
| Histórico tras recuperación | 3.186 filas coincidentes entre PostgreSQL e InfluxDB; cero puntos adicionales. |
| Sensor real | Nuevas muestras de UM1, incluyendo IDs 3184–3186. |
| Dashboard y alertas | Visualización, tres reglas cargadas y prueba de falta de datos confirmadas. |
| Arranque automático | Configuración comprobada en ambas EC2; reinicio completo pendiente de confirmar. |

La consigna original de la actividad 2 no está en el repositorio. Discord se registra como complemento opcional de la implementación, no como requisito académico demostrado.

## Distribución final de servicios

| Servidor | Dirección | Servicios y versiones observadas |
| --- | --- | --- |
| Pública | IP elástica `3.231.16.96`; privada `192.168.0.200` | Caddy, FastAPI, receptor Python MQTT, Mosquitto y Grafana 13.2.5. |
| Privada | `192.168.1.142` | PostgreSQL 16.15 e InfluxDB 2.7.12. Ubuntu 26.04.1 LTS observado en el acceso SSH. |

| Acceso | Ruta o puerto |
| --- | --- |
| Dashboard original | `https://3.231.16.96/?device_code=UM1` |
| Grafana | `https://3.231.16.96/grafana/` |
| MQTT del ESP32 | TLS en TCP `8883`. |
| PostgreSQL | `192.168.1.142:5432`, por la VPC. |
| InfluxDB | `192.168.1.142:8086`, por la VPC. |
| API para diagnóstico SSH | `http://127.0.0.1:8000`. |

Se indicó permitir TCP 8086 desde `192.168.0.200/32` en la privada y se confirmó la conexión desde la pública. No se exportó una auditoría completa de los grupos de seguridad. Los enlaces interiores a PostgreSQL e InfluxDB no incorporan TLS adicional en esta plantilla.

## 1. Revisión y actualización del código

La copia local estaba limpia y se actualizó por avance directo hasta `4973629`. En la EC2 pública se confirmó posteriormente el mismo commit y `Already up to date`.

```bash
cd ~/Actividad_1_IoT_IA
git status --short --branch
git pull --ff-only origin main
git log -1 --oneline
```

La revisión local ejecutó las 40 pruebas del backend con SQLite temporal: todas pasaron, con una advertencia de deprecación de TestClient/httpx. Los dos Compose de AWS se validaron localmente con valores ficticios. Esas pruebas no sustituyen la ejecución remota ni constituyen una nueva ejecución de la suite contra PostgreSQL.

## 2. Respaldo previo de PostgreSQL

El primer intento de `docker compose exec` con redirección dejó un archivo de cero bytes. La consulta a `pg_stat_activity` no mostró una sesión `pg_dump` y la base ocupaba 8.591 kB. No se determinó la causa de esa espera; no se atribuye a un bloqueo de PostgreSQL ni a un defecto confirmado de Compose.

Se repitió mediante el contenedor conocido, con salida detallada, sin espera por contraseña y con límite para adquirir bloqueos:

```bash
sudo docker exec rutasalud-db-db-1 pg_dump \
  -U postgres -d monitor -w -Fc \
  --verbose --lock-wait-timeout=10s \
  -f /tmp/monitor-actividad2.dump

sudo docker exec rutasalud-db-db-1 pg_restore --list /tmp/monitor-actividad2.dump
```

El archivo se copió a `/home/ubuntu/rutasalud-backups/20261031T024441Z/monitor.dump`, con propietario `ubuntu` y permisos `600`. Se observaron **54 KB**, formato CUSTOM y 27 entradas en el índice. La lectura del índice fue correcta; **no se ejecutó una restauración completa de ese archivo** ni se confirmó su copia fuera de la EC2.

## 3. Recursos y swap en ambas EC2

Los dos servidores tenían unos 908 MiB de RAM y ninguna swap. Se creó una swap de **1 GiB** en cada uno, comprobando antes que el sistema de archivos fuese ext4 o XFS. La creación usó un archivo nuevo y exclusivo:

```bash
sudo dd if=/dev/zero of=/swapfile-rutasalud bs=1M count=1024 conv=excl status=progress
sudo chmod 600 /swapfile-rutasalud
sudo mkswap /swapfile-rutasalud
sudo swapon /swapfile-rutasalud
```

Estos comandos documentan la creación inicial; el archivo ya existe en las dos instancias. La activación al arrancar quedó registrada en `/etc/fstab`:

```text
/swapfile-rutasalud none swap sw,nofail 0 0
```

Se comprobó con `free -h` y `swapon --show`. La swap aporta margen usando disco; no equivale a ampliar RAM ni acredita capacidad para cargas mayores. Procedimiento de referencia: [swap en EC2](https://repost.aws/knowledge-center/ec2-memory-swap-file).

## 4. Instalación de InfluxDB en la privada

La instalación anterior tenía un Compose independiente en `~/rutasalud-db`. Por eso actualizar Git en la pública no actualizaba esta carpeta.

Se descargó `deploy/aws-db/compose.yaml` del commit `4973629` como candidato, se agregaron al `.env` únicamente las variables ausentes `INFLUX_ADMIN_PASSWORD` e `INFLUX_ADMIN_TOKEN`, se validó el candidato y se reemplazó el Compose existente. Las credenciales previas de PostgreSQL se conservaron.

Desde `~/rutasalud-db` se inició únicamente el nuevo servicio:

```bash
sudo docker compose up -d --no-deps --wait --wait-timeout 180 influxdb
sudo docker exec rutasalud-db-influxdb-1 influx ping
```

Se observaron PostgreSQL e InfluxDB saludables, con este último enlazado a `192.168.1.142:8086`. Su consumo inicial observado fue de 47,13 MiB; es una medición puntual de arranque, no un máximo garantizado.

### Organización, bucket y tokens

- Organización: `rutasalud`.
- Bucket: `telemetria`.
- Measurement: `ambiente`; tag: `device_code`; campos: temperatura, humedad e ID de lectura.
- Token de aplicación: lectura y escritura limitadas al bucket. La lectura permite ejecutar el verificador.
- Token de Grafana: solo lectura del bucket.
- Token administrativo: permanece en la configuración privada de InfluxDB.

La creación se hizo con `influx auth create`, usando `--read-bucket` para ambos tokens y `--write-bucket` solo para la aplicación. Un bloque Python capturó el JSON de la CLI y guardó los tokens sin imprimir sus valores. Referencia: [permisos de tokens de InfluxDB](https://docs.influxdata.com/influxdb/v2/reference/cli/influx/auth/create/).

Archivos privados creados:

```text
/home/ubuntu/.config/rutasalud-tokens/app.token
/home/ubuntu/.config/rutasalud-tokens/grafana.token
```

Se transfirieron por SCP a la pública, dentro de `.secrets/aws-influx/`, con permisos `600`. La conexión desde la pública respondió con `status: pass`, versión `v2.7.12` y el mensaje `ready for queries and writes`.

## 5. Conexión de la aplicación y carga del histórico

En la pública se leyó el token desde `.secrets/aws-influx/app.token` y se agregaron `INFLUX_URL` e `INFLUX_TOKEN` a `deploy/aws-app/.env`. Se conservó una copia previa en `.backups/actividad2/aws-app-antes-influx.env` y no se imprimieron las claves.

Se reconstruyó la imagen compartida por API, receptor y migraciones, y se actualizaron los servicios:

```bash
cd ~/Actividad_1_IoT_IA
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml build api
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml --profile app up -d --no-build --wait --wait-timeout 180 api mqtt-worker
```

Hubo una desconexión SSH durante la construcción. Después se aportó el estado de los servicios actualizados y saludables. No se confirmó la causa del corte ni se registró un diagnóstico de falta de memoria.

La consulta local `/health` respondió:

```json
{"status":"ok","database":"ok","csv":"ok","influx":"ok"}
```

`influx: ok` comprueba accesibilidad del servicio. La escritura y consulta autenticadas se verificaron después con la reconciliación y comparación del histórico:

```bash
sudo docker exec rutasalud-app-api-1 python scripts/reconcile_influx.py
sudo docker exec rutasalud-app-api-1 python scripts/verify_influx.py
sudo docker exec rutasalud-app-api-1 python scripts/verify_csv.py
```

Resultado del primer corte:

```text
InfluxDB reconstruido desde la base de datos: 2951 mediciones
Coincidencia exacta: 2951 mediciones (0 puntos adicionales en InfluxDB)
Coincidencia exacta: 2951 mediciones
```

Se indicó apagar temporalmente el ESP32 para comparar sin escrituras simultáneas. Después, el observador de la API confirmó nuevas muestras sin generar datos sintéticos.

## 6. Espacio de disco y ampliación de la pública

La raíz tenía unos 6,7 GiB útiles. Se eliminó caché de construcción y una imagen de PostgreSQL sin contenedores asociados en la pública; la base del proyecto permanece en la privada. Después de esa limpieza se observaron 2,1 GiB libres.

La descarga de `grafana/grafana:13.2.5` dejó solo **259 MiB libres, 97 % de ocupación**. Ese margen resultó insuficiente para continuar con la operación del laboratorio. Se amplió el volumen EBS de la pública; el tamaño finalmente observado fue **15 GiB**, no los 20 GiB propuestos inicialmente.

Con el dispositivo y el tipo de sistema de archivos identificados mediante `lsblk` y `findmnt`, se extendieron la partición y ext4:

```bash
sudo growpart /dev/nvme0n1 1
sudo resize2fs /dev/nvme0n1p1
```

Resultado confirmado: partición de 13,9 GiB, raíz de unos 14 GiB y 7,1 GiB libres en ese corte. Las otras particiones corresponden al arranque. No se recibió identificador ni estado de una instantánea EBS previa; su existencia no se registra como verificada. Referencia: [ampliar partición y sistema de archivos en EBS](https://docs.aws.amazon.com/ebs/latest/userguide/recognize-expanded-volume-linux.html).

## 7. Configuración de Grafana y HTTPS

Se leyó el token de solo lectura desde `.secrets/aws-influx/grafana.token`, se pidió el webhook con entrada oculta y se generó una contraseña de administrador. Se agregaron estas variables a `deploy/aws-app/.env` con los helpers `read_env` y `append_env`, respaldando antes el archivo:

```text
GRAFANA_ADMIN_PASSWORD
GRAFANA_INFLUX_TOKEN
GRAFANA_ALERT_WEBHOOK_URL
```

Para una instalación nueva, el script del repositorio ofrece la configuración equivalente mediante preguntas en la terminal:

```bash
python3 scripts/setup_grafana.py --env-file deploy/aws-app/.env
```

El Compose aprovisiona automáticamente la fuente InfluxDB, el dashboard y las reglas desde `grafana/provisioning`. Se inició Grafana y se reinició el proxy:

```bash
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml --profile grafana up -d --no-deps --no-build --wait --wait-timeout 180 grafana
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml --profile app restart caddy
```

La creación de `rutasalud-app_grafana_data` y el estado `healthy` quedaron confirmados. El acceso HTTPS respondió:

```json
{"database":"ok","version":"13.2.5","commit":"3ab9ef02dbcaf449e531f2367481a110c2b6c79c"}
```

Ese endpoint valida la salud interna de Grafana; la lectura de InfluxDB y la visualización se comprobaron adicionalmente mediante el dashboard y las alertas. En el corte posterior al arranque había 371 MiB de RAM disponibles y 438 MiB de swap usados en la pública; no se midió una carga sostenida.

## 8. Prueba física de falta de datos y recuperación

La [captura de Grafana](evidencias/actividad2-aws-reglas-normal.png) mostró las tres reglas aprovisionadas en `Normal`. Se apagó el ESP32 para interrumpir la recepción. La captura posterior de Discord mostró:

```text
Firing
alertname = Sin mediciones de UM1
device_code = UM1
grafana_folder = RutaSalud
grafana_state_reason = NoData
summary = UM1 no ha enviado mediciones en los ultimos 2 minutos.
```

Tras encender nuevamente el ESP32 se observaron estas muestras:

| ID | Temperatura | Humedad | Recepción UTC, 31 de octubre | Hora de Colombia, 30 de octubre |
| --- | --- | --- | --- | --- |
| 3184 | 27,6 °C | 68 % | 04:16:26.511506 | 23:16:26.511506 |
| 3185 | 27,6 °C | 68 % | 04:16:36.528105 | 23:16:36.528105 |
| 3186 | 27,6 °C | 68 % | 04:16:46.523392 | 23:16:46.523392 |

```text
Recepcion de nuevas mediciones verificada en la API.
Coincidencia exacta: 3186 mediciones (0 puntos adicionales en InfluxDB)
```

El usuario confirmó después los tres puntos de cierre: retorno de la regla a `Normal`, mensaje `Resolved` recibido y gráficas con datos recientes. El disparo y la resolución no se cronometraron en AWS. La comparación CSV aportada sigue siendo la del corte de 2.951; no se afirma una nueva comparación CSV de 3.186.

## 9. Persistencia y arranque automático comprobados

| Instancia | Información | Persistencia |
| --- | --- | --- |
| Privada | PostgreSQL | `rutasalud-db_postgres_data`. |
| Privada | Series InfluxDB y configuración CLI | `rutasalud-db_influx_data` y `rutasalud-db_influx_config`. |
| Pública | CSV | `rutasalud-app_csv_data`. |
| Pública | Usuarios y estado de Grafana | `rutasalud-app_grafana_data`. |
| Pública | Sesión y cola de Mosquitto | `rutasalud-app_mqtt_data`. |
| Pública | Caddy y validación ACME | Volúmenes del proyecto y archivos privados bajo `.secrets`. |
| Ambas | Configuración y credenciales | Archivos del disco EBS; fuera del historial Git. |

Se ejecutó en ambas EC2:

```bash
sudo systemctl enable --now docker.service containerd.service
systemctl is-enabled docker.service containerd.service
sudo docker ps -q | xargs -r sudo docker inspect --format '{{.Name}} -> {{.HostConfig.RestartPolicy.Name}}'
grep -E '^/swapfile-rutasalud[[:space:]]' /etc/fstab
```

Se recibieron `enabled` para ambos servicios, `unless-stopped` para los cinco contenedores permanentes públicos y los dos privados, y la entrada de swap en cada servidor. En la pública, `rutasalud-cert-renew.timer` quedó confirmado como `enabled` y `active`.

Los contenedores de migración y las tareas puntuales no son servicios permanentes. No se añadió un segundo gestor de arranque de contenedores. La política de Docker respeta las paradas manuales y actúa cuando termina el proceso; un estado `unhealthy` por sí solo no equivale a un reinicio automático. Referencias: [políticas de reinicio](https://docs.docker.com/engine/containers/start-containers-automatically/), [arranque de Docker con systemd](https://docs.docker.com/engine/install/linux-postinstall/#configure-docker-to-start-on-boot-with-systemd) y [volúmenes persistentes](https://docs.docker.com/engine/storage/volumes/).

El temporizador revisa los certificados al arrancar y dos veces al día, con demoras configuradas. Se comprobó su habilitación y actividad; no se forzó ni se acreditó una nueva renovación ACME en esta sesión.

## Operación habitual desde la pública

Estos comandos consultan el despliegue ya existente y no generan muestras:

```bash
cd ~/Actividad_1_IoT_IA
sudo docker ps --format 'table {{.Names}}\t{{.Status}}'
curl --connect-timeout 5 --max-time 15 -fsS http://127.0.0.1:8000/health
curl --connect-timeout 5 --max-time 15 -fsS https://3.231.16.96/grafana/api/health
python3 scripts/verify_device.py --device UM1 --samples 3 --timeout 90
sudo docker exec rutasalud-app-api-1 python scripts/verify_influx.py
free -h
df -h /
```

Para comparar CSV y SQL sin diferencias transitorias, detener temporalmente la llegada de muestras y ejecutar `verify_csv.py`. Para reparar una proyección, usar `reconcile_csv.py` o `reconcile_influx.py` desde el contenedor API.

Las actualizaciones que deban incluir Grafana usan ambos perfiles de AWS:

```bash
sudo docker compose --env-file deploy/aws-app/.env -f deploy/aws-app/compose.yaml --profile app --profile grafana up -d --no-build --wait --wait-timeout 180
```

Ese comando supone las imágenes necesarias ya disponibles; una actualización de código del backend requiere antes `build api`. Conservar los nombres de proyecto, los archivos privados y los volúmenes existentes. La persistencia en el disco no reemplaza un respaldo externo.

## Pendientes y prueba de reinicio para otra sesión

- **Reinicio completo de las EC2:** se propuso reiniciar primero la privada y después la pública, pero no se recibió el resultado. La configuración está comprobada; el comportamiento después del reinicio no se registra como pasado.
- **Restauración y respaldo externo:** falta restaurar el dump en una base descartable y confirmar su copia fuera de la instancia. Las credenciales y certificados también necesitan un respaldo privado.
- **Alarmas de temperatura y humedad en AWS:** las reglas quedaron cargadas; el disparo físico de ambas no se probó en AWS. Los ensayos sintéticos locales están separados en [validación](validation.md).
- **Operación prolongada:** faltan estabilidad durante jornadas, pérdida real de Wi-Fi con cola y ensayo en vehículo. Apagar el ESP32 no equivale a probar la recuperación de una cola durante una caída de red.
- **Capacidad:** las dos EC2 siguen teniendo alrededor de 1 GiB de RAM. Los consumos observados no sustituyen una evaluación de carga sostenida y crecimiento de históricos.
- **Rúbrica:** falta contrastar la consigna original de la actividad 2, especialmente sus entregables y la necesidad de un canal externo de notificación.

Para cerrar la prueba de arranque en otra sesión: guardar el conteo SQL, reiniciar la privada y comprobar `uptime`, servicios, contenedores, swap y datos sin ejecutar `compose up`. Después repetir con la pública y volver a verificar API, Grafana y coincidencia SQL/InfluxDB. El conteo puede aumentar por nuevas muestras; no debe perder el histórico anterior.
