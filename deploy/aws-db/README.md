# PostgreSQL privado en AWS

Plantilla para la segunda EC2 Ubuntu, con Docker Engine y Compose instalados. La IP privada informada para el laboratorio es `192.168.1.142`; la aplicación se instalará en la otra EC2 (`192.168.0.200` como IP privada). Las direcciones son configuración de esta instalación, no direcciones públicas.

El usuario confirmó acceso SSH desde el público, salida al repositorio de Docker e instalación de PostgreSQL en AWS: `rutasalud-db-db-1` saludable, publicado sobre `192.168.1.142:5432`, base `monitor` con propietario `monitor` y permisos de superusuario/creación de bases/roles deshabilitados para ese usuario. La imagen de EC2 confirma que el servidor público tiene IP privada `192.168.0.200` e IP elástica `3.231.16.96`. El usuario confirmó también autenticación TCP desde el público. El despliegue de la aplicación sigue la [guía separada de aplicación pública](../aws-app/README.md). La prueba Docker local de la plantilla es independiente de estas evidencias remotas.

## Instalación

Instalar Docker siguiendo [el repositorio oficial de Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Esta configuración requiere una instancia nueva para la base de datos, en la misma VPC que la aplicación y sin IP pública. En el grupo de seguridad autorizar TCP 5432 solo desde el grupo de seguridad de la aplicación. SSH administrativo se realiza mediante el servidor público o el mecanismo privado configurado.

En la EC2 privada crear `~/rutasalud-db` y colocar allí `compose.yaml` e `init-app.sql` de esta carpeta. Si se clonó el repositorio, también se pueden ejecutar los comandos directamente dentro de `deploy/aws-db`. Desde esa carpeta generar los secretos:

```bash
python3 - <<'PY'
from pathlib import Path
import secrets
path = Path('.env')
if path.exists():
    print('.env ya existe; se conserva sin cambios')
else:
    with path.open('x', encoding='utf-8') as stream:
        stream.write('DB_BIND_IP=192.168.1.142\nDB_PUBLISH_PORT=5432\n'
                     + 'POSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n'
                     + 'MONITOR_PASSWORD=' + secrets.token_hex(24) + '\n')
    path.chmod(0o600)
    print('.env creado; contrasenas no impresas')
PY
chmod 600 .env
sudo docker compose config --quiet
sudo docker compose up -d --wait --wait-timeout 120
sudo docker compose ps
```

El puerto se publica sobre la IP privada indicada, no sobre todas las interfaces. `rutasalud-db_postgres_data` conserva los datos. El administrador es `postgres`; `monitor` es el propietario de la base/esquema para ejecutar las migraciones del proyecto, con LOGIN y sin superusuario, creación de bases ni creación de roles. En el futuro se puede separar también el usuario migrador del rol de ejecución.

## Comprobación

Desde el servidor privado:

```bash
sudo docker compose exec db psql -U postgres -d monitor -c "SELECT datname,pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname='monitor'; SELECT rolname,rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname='monitor';"
```

Se espera base `monitor`, propietario `monitor` y los tres permisos administrativos en `f`. La comprobación local por socket usa el administrador; la autenticación del usuario de aplicación se prueba por TCP desde el público:

```bash
sudo docker run --rm -it postgres:16-alpine psql -h 192.168.1.142 -U monitor -d monitor -W -c "SELECT current_user,current_database();"
```

Introducir la clave `MONITOR_PASSWORD` del `.env` privado cuando psql la solicite. No utilizar la clave administrativa para la aplicación. No compartir el archivo `.env` ni pegar contraseñas en el chat o en Git.

El futuro `DATABASE_URL` de la aplicación será `postgresql+psycopg://monitor:CLAVE_MONITOR@192.168.1.142:5432/monitor`; los secretos hexadecimales generados no requieren codificación adicional en la URL. Las tablas `devices`, `sensor_readings` y Alembic se crearán después, al ejecutar las migraciones desde la aplicación. Este Compose no inicia API, CSV ni broker en el servidor de la BD.

## InfluxDB

El mismo Compose inicia InfluxDB 2.7 en esta EC2 privada, publicado solo sobre la IP privada en el puerto 8086. En el grupo de seguridad autorizar TCP 8086 únicamente desde el grupo de seguridad de la aplicación. Actualizar `compose.yaml` en `~/rutasalud-db` y agregar los secretos sin tocar los existentes:

```bash
python3 - <<'PY'
from pathlib import Path
import secrets
path = Path('.env')
if 'INFLUX_ADMIN_TOKEN=' in path.read_text(encoding='utf-8'):
    print('InfluxDB ya configurado; se conserva sin cambios')
else:
    with path.open('a', encoding='utf-8') as stream:
        stream.write('INFLUX_ADMIN_PASSWORD=' + secrets.token_hex(24) + '\n'
                     + 'INFLUX_ADMIN_TOKEN=' + secrets.token_hex(32) + '\n')
    print('Claves InfluxDB agregadas; no impresas')
PY
sudo docker compose up -d --wait --wait-timeout 120
sudo docker compose ps
```

Crear un token limitado al bucket `telemetria` para la aplicación. El token administrativo no sale de esta instancia:

```bash
BUCKET_ID=$(sudo docker compose exec -T influxdb influx bucket list --name telemetria --hide-headers | cut -f1)
sudo docker compose exec -T influxdb influx auth create --org rutasalud --description rutasalud-app --write-bucket "$BUCKET_ID" --read-bucket "$BUCKET_ID"
```

Crear además un token de solo lectura para Grafana:

```bash
sudo docker compose exec -T influxdb influx auth create --org rutasalud --description rutasalud-grafana --read-bucket "$BUCKET_ID"
```

Copiar cada token de la salida directamente en `setup_influx.py` ([paso 8 de la aplicación](../aws-app/README.md)) y `setup_grafana.py` (paso 9). No pegarlos en el chat ni en Git. `influx_data` conserva las series e `influx_config` la configuración del CLI. Las variables `DOCKER_INFLUXDB_INIT_*` solo se aplican con un volumen vacío.

Antes de iniciarlo, comprobar la memoria disponible con `free -h`: la EC2 ya ejecuta PostgreSQL.

## Reintentos y datos existentes

Los scripts de inicialización solo se ejecutan con un volumen vacío. Cambiar las variables no rota las claves de una base ya inicializada. Si falla la inicialización, revisar `sudo docker compose logs --tail=80 db` y reparar sobre la base existente; no eliminar el volumen como primer paso. Nunca utilizar `down -v` para conservar datos.

El volumen de esta EC2 empieza vacío: el histórico local Windows no se copia automáticamente. Conservar también las claves de `.env` y realizar respaldos con `pg_dump` antes de migrar histórico. La aplicación AWS, HTTPS y MQTT TLS se preparan por separado según [el plan de nube](../../docs/cloud-migration.md).

Referencias: [imagen oficial PostgreSQL e inicialización](https://hub.docker.com/_/postgres), [variables de entorno en psql](https://www.postgresql.org/docs/16/app-psql.html).
