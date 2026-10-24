# Recuperación de Docker — 23 de octubre de 2026

## Problema observado

La API de taller1 estaba detenida y su inspección mostraba `NetworkSettings.Networks = {}`. PostgreSQL y migrate conservaban su asociación con taller1_default. El log de la API mostraba `failed to resolve host 'db'`. Además, docker compose images fallaba con No such image al consultar una referencia antigua de migrate.

Se compararon main.py, las rutas API y app.js de la imagen taller1-api:latest con los archivos locales: los tres hashes coincidieron. No se encontró evidencia de sustitución de esos archivos por código de otro proyecto. Esta revisión no identifica qué chat u operación desconectó la red o cambió las referencias.

## Reparación aplicada

- Respaldo previo de PostgreSQL en formato pg_dump y del CSV físico, dentro de .backups/docker-repair-20261023-190109. Había 783 mediciones en ambos almacenamientos. El índice del dump contiene las tablas y secuencias esperadas.
- Proyecto Compose fijado explícitamente como taller1 para conservar los nombres de red y volúmenes al ejecutar desde otra carpeta.
- Imágenes con nombres específicos: actividad1-iot-ia-api:local y actividad1-iot-ia-migrate:local. Se agregaron etiquetas de origen del repositorio.
- Reconstrucción sin caché y recreación de los tres contenedores del proyecto, conservando taller1_postgres_data y taller1_csv_data.
- .backups queda excluido de Git y del contexto de construcción Docker.

No se borraron volúmenes ni se restauraron datos encima de la base existente. Las imágenes antiguas y los demás proyectos no se eliminaron.

## Comprobaciones

- API y PostgreSQL asociados a taller1_default.
- /health, /api/v1/devices, /api/v1/readings/latest y dashboard de UM1 responden 200.
- Migraciones finalizadas correctamente.
- Coincidencia exacta PostgreSQL/CSV: 783 mediciones, mismo conteo que antes de recrear.
- Suite pytest con PostgreSQL en monitor_test: 15 pasaron en 1.17 s, una advertencia de deprecación del cliente TestClient/httpx.
- docker compose images vuelve a enumerar las imágenes correctamente.

La última muestra conservada de UM1 es del 20 de octubre, 16:40:28 UTC. La reparación valida el servidor y los datos persistidos; no confirma una nueva transmisión del ESP32 durante esta sesión.

## Comandos de comprobación y recuperación

Desde la raíz de este repositorio:

```powershell
docker compose ps -a
docker compose logs --tail 50 api migrate
Invoke-RestMethod http://localhost:8000/health
docker compose exec api python scripts/verify_csv.py
```

Si vuelve a ser necesaria una reconstrucción, después de respaldar los datos:

```powershell
docker compose build --no-cache api migrate
docker compose up -d --force-recreate
```

Los comandos conservan los volúmenes existentes. No utilizar down -v, volume prune ni system prune --volumes para este procedimiento.
