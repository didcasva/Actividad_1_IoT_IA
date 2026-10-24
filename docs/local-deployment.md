# Ejecución local

Ejecutar desde la raíz del repositorio. Requiere Git, Python 3.12 y Docker Desktop con contenedores Linux (Windows), o Docker Engine y Compose plugin (Ubuntu).

## Windows PowerShell

```powershell
python scripts/setup_env.py
docker compose config --quiet
docker compose up -d --build
docker compose ps -a
Invoke-RestMethod http://localhost:8000/health
$env:API_KEY = (Get-Content .env | Where-Object { $_ -like 'API_KEY=*' }) -replace '^API_KEY=', ''
python scripts/simulate.py --count 10 --interval 1
docker compose exec api python scripts/verify_csv.py
```

Las migraciones se ejecutan mediante el servicio migrate antes de arrancar api. Para ejecutarlas manualmente:

```powershell
docker compose run --rm migrate
docker compose logs api migrate
```

## Ubuntu Server físico o VM

Para la instalación completa desde cero en Oracle VirtualBox, incluyendo red puente, Docker, transferencia de la versión local y registro del ESP32 UM1, seguir [la guía paso a paso para Ubuntu](ubuntu-virtualbox.md).

Instalar Docker siguiendo [el repositorio oficial para Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Con el repositorio oficial configurado:

```bash
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin git python3
git clone https://github.com/didcasva/Actividad_1_IoT_IA.git
cd Actividad_1_IoT_IA
python3 scripts/setup_env.py
sudo docker compose config --quiet
sudo docker compose up -d --build
curl --fail http://localhost:8000/health
export API_KEY=$(sed -n 's/^API_KEY=//p' .env)
python3 scripts/simulate.py --count 10 --interval 1
sudo docker compose exec api python scripts/verify_csv.py
```

Después de clonar, generar un .env propio en Ubuntu. No transferir .venv ni publicar los archivos .env o config.h.

Una VM Ubuntu debe usar adaptador puente para acceso LAN o redirección explícita del puerto 8000. Permitir entrada TCP 8000 solo desde la subred local. En Windows autorizar Docker en redes privadas; no desactivar el firewall. En Ubuntu con UFW revisar también las reglas DOCKER-USER: los puertos publicados de Docker pueden omitir las reglas UFW.

## Prueba de persistencia real

Detener el simulador para que no cambie el conteo. Registrar el resultado antes y después:

```sh
docker compose exec db psql -U monitor -d monitor -c "SELECT count(*) FROM sensor_readings;"
docker compose exec api python scripts/verify_csv.py
docker compose restart db api
docker compose ps
```

Esperar a que /health responda y repetir conteo y comparación. Deben ser iguales. También se puede hacer `docker compose down` y `docker compose up -d`; **no usar down -v**, pues borra volúmenes. Esta prueba exige un motor Docker activo.

## Problemas habituales

- Error named pipe / engine: iniciar Docker Desktop y esperar que el motor Linux esté listo.
- Error `failed to resolve host db` o referencias de imagen ausentes: ver [recuperación de Docker](docker-recovery.md), con respaldo y recreación de contenedores conservando los volúmenes.
- 401: comprobar X-API-Key idéntica a API_KEY de .env.
- 404 ingestión: verificar device_code y is_active en devices.
- 422: revisar formato JSON, rangos y fechas con zona UTC.
- 503: revisar logs, conexión SQL y permisos de /data; reintentar misma identidad.
- ESP32 no conecta: comprobar 2.4 GHz, IP LAN, aislamiento de clientes y firewall.
- Gráficas ausentes: comprobar /static/chart.umd.min.js y la consola del navegador. Chart.js 4.4.8 se incluye localmente con su licencia, para operar sin Internet.
- Puerto ocupado: cambiar API_PORT en .env y API_URL del firmware.
- Cambiar POSTGRES_PASSWORD no cambia una BD ya inicializada; modificar el rol con psql y actualizar DATABASE_URL sin borrar el volumen.
