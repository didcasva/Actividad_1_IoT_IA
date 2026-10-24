# Instalación en Ubuntu Server con Oracle VirtualBox

Para incorporar el nuevo requisito MQTT, completar la instalación base de esta guía y después seguir [activación del broker y topics](mqtt.md). El perfil MQTT agrega Mosquitto/receptor y se activa con `sudo docker compose --profile mqtt up -d --build` después de generar sus archivos privados. Las instrucciones de firmware HTTP de esta guía corresponden al transporte anterior; para MQTT usar `mqtt.config.h` y los pasos de la guía enlazada. Para detener todos los servicios, incluir `--profile mqtt`.

Esta guía despliega la versión local actual de Ruta Salud en una VM nueva. El ESP32 envía por Wi-Fi a la IP de Ubuntu; FastAPI, PostgreSQL y el CSV se ejecutan allí con Docker Compose. No hace falta instalar PostgreSQL ni las dependencias Python de la aplicación directamente en Ubuntu.

El repositorio no contiene las mediciones de Windows, `.env`, credenciales Wi-Fi ni `config.h`. Ubuntu tendrá una base nueva. Los datos existentes de Windows permanecen en sus volúmenes; trasladar ese histórico requiere una migración aparte.

## 1. Preparar VirtualBox y la red

- Usar Ubuntu Server 24.04 LTS o 26.04 LTS de 64 bits. Recursos sugeridos: 2 CPU, 4 GB de RAM y 30 GB de disco, según la capacidad del PC.
- Con la VM apagada: Configuración → Red → Adaptador 1 → habilitar → **Adaptador puente**. Seleccionar la tarjeta física que conecta el PC al router (Ethernet si está conectado por cable, o Wi-Fi si esa es la conexión utilizada). Activar «Cable conectado».
- Durante la instalación crear un usuario y habilitar OpenSSH Server. Instalar Docker después con el repositorio oficial, como se indica abajo.
- Ubuntu y el ESP32 deben poder comunicarse en la LAN. Una red de invitados con aislamiento puede impedirlo. NAT sin redirección de puertos no permite al ESP32 alcanzar directamente la IP interna de la VM.

Referencia: [redes de Oracle VirtualBox](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/networkingdetails.html).

## 2. Preparar Ubuntu e identificar su IP

En la consola de Ubuntu:

```bash
sudo apt update
sudo apt install -y openssh-server git python3 curl ca-certificates nano
sudo systemctl enable --now ssh
sudo timedatectl set-timezone America/Bogota
ip -br -4 address
ip route
```

Anotar la IPv4 de la interfaz conectada al router. `IP_UBUNTU` en los ejemplos significa esa dirección real: no copiar literalmente ese texto. Si la LAN sigue siendo `192.168.20.0/24`, normalmente será `192.168.20.x`. La VM debe tener una IP distinta de Windows. Una dirección `10.0.2.15` suele indicar NAT; revisar el paso 1. Las direcciones de redes internas Docker, como `172.x`, no sirven como destino del ESP32.

Reservar esta IP en el DHCP del router usando la MAC de la VM para evitar que cambie. No asignar una dirección arbitraria que pueda estar ocupada.

## 3. Instalar Docker Engine y Compose

Ejecutar en **Ubuntu**, no en PowerShell. Estas instrucciones son para una instalación nueva sin otro Docker preinstalado. Si ya se instaló Docker por Snap o `docker.io`, revisar los paquetes en conflicto según la documentación oficial antes de continuar.

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
sudo docker compose version
```

Referencia: [instalación oficial de Docker en Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Se usa `sudo` con Docker durante toda esta guía.

## 4. Descargar el proyecto desde GitHub

Se puede continuar en la consola de Ubuntu o conectarse desde **PowerShell en Windows**:

```powershell
$ipUbuntu = Read-Host "IP de Ubuntu"
$usuarioUbuntu = Read-Host "Usuario creado en Ubuntu"
ssh "${usuarioUbuntu}@${ipUbuntu}"
```

Comprobar la huella SSH mostrada comparándola con la consola de la VM (`sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`) y aceptar la conexión si coincide. Introducir la contraseña del usuario de Ubuntu cuando se solicite; no se ve mientras se escribe.

Desde aquí la terminal SSH ejecuta comandos en **Ubuntu**:

```bash
cd ~
git clone https://github.com/didcasva/Actividad_1_IoT_IA.git
cd ~/Actividad_1_IoT_IA
ls
```

Debe aparecer `compose.yaml` junto con `backend`, `frontend`, `firmware`, `scripts` y `docs`.

## 5. Crear la configuración del servidor

```bash
python3 scripts/setup_env.py
chmod 600 .env
nano .env
```

El script genera contraseña de PostgreSQL y API Key. No modifica un `.env` existente. Mantener `API_PORT=8000`. En `DATABASE_URL` el servidor debe seguir siendo **`db:5432`**, que es el nombre interno del servicio PostgreSQL.

Copiar de forma privada el valor de `API_KEY` para configurarlo después en el firmware. No publicarlo. Salir de nano con Ctrl+X; si hubo cambios, guardar con Y y Enter. La contraseña de `POSTGRES_PASSWORD` debe coincidir con la incluida en `DATABASE_URL`.

## 6. Construir y arrancar los contenedores

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps -a
curl --fail http://localhost:8000/health
```

La primera construcción necesita Internet y puede tardar varios minutos. Si aún no está listo:

```bash
sudo docker compose logs --tail=100 db migrate api
```

Resultado esperado:

- `db` y `api`: en ejecución y saludables (`healthy`, una vez terminen las comprobaciones).
- `migrate`: `Exited (0)`, porque termina después de crear/actualizar las tablas. Es normal.
- `/health`: `{"status":"ok","database":"ok","csv":"ok"}`.

Los volúmenes `taller1_postgres_data` y `taller1_csv_data` conservan los datos al recrear contenedores.

## 7. Registrar el dispositivo físico UM1

Las migraciones iniciales registran `esp32-01`; en esta base nueva también hay que registrar `UM1`:

```bash
sudo docker compose exec db psql -U monitor -d monitor -c "INSERT INTO devices (device_code,name,sensor_type,location,created_at,is_active) VALUES ('UM1','Unidad movil de salud UM1','DHT11','Area de atencion',CURRENT_TIMESTAMP,true) ON CONFLICT (device_code) DO NOTHING;"
curl --fail http://localhost:8000/api/v1/devices
```

Debe aparecer `device_code` igual a `UM1`, con `sensor_type` igual a `DHT11` e `is_active` igual a `true`.

## 8. Abrir el aplicativo desde Windows

En otra ventana de **PowerShell**, reemplazar `IP_UBUNTU`:

```powershell
Test-NetConnection IP_UBUNTU -Port 8000
Invoke-RestMethod "http://IP_UBUNTU:8000/health"
```

En el navegador de Windows:

```text
http://IP_UBUNTU:8000/?device_code=UM1
http://IP_UBUNTU:8000/docs
```

`localhost` en Windows sigue apuntando a Windows. Para ver esta instalación hay que abrir la **IP de Ubuntu**.

No desactivar firewalls. Si SSH está bloqueado y UFW está activo, permitir SSH desde la subred local real antes de usarlo. Los puertos publicados por Docker pueden omitir UFW: restringirlos exige revisar también las reglas de Docker/`DOCKER-USER`, como explica la documentación oficial. Este despliegue publica el puerto 8000; PostgreSQL no publica 5432 al host. Mantenerlo en la LAN, sin redirección de puertos del router a Internet.

## 9. Cambiar el destino del ESP32

El ESP32 puede seguir conectado por USB al PC Windows para programarlo. No necesita USB conectado a la VM: transmite por Wi-Fi.

En Arduino IDE abrir el proyecto existente y editar su archivo privado `firmware/esp32_dht_monitor/config.h` en Windows:

```cpp
#define API_URL "http://IP_UBUNTU:8000/api/v1/readings"
#define API_KEY "VALOR_API_KEY_DEL_ENV_DE_UBUNTU"
#define DEVICE_CODE "UM1"
#define DHT_PIN 4
#define DHT_TYPE DHT11
```

Reemplazar los dos marcadores por los valores reales y mantener las credenciales de la red Wi-Fi de 2.4 GHz. Cargar de nuevo el firmware a la ESP32-S3 y abrir el monitor serie a 115200. Usar la configuración de placa que ya funcionó; no es necesario cambiar sensor ni cableado.

Debe obtener una IP y enviar lecturas con `POST 200`. Si tiene muestras pendientes, primero puede enviar la cola anterior. Un `401` indica diferencia de API Key; `404`, código de dispositivo no registrado/activo; `POST -1`, fallo de transporte que requiere revisar IP, conectividad, puerto y servidor. Estar asociado al punto Wi-Fi todavía no garantiza haber recibido IP por DHCP.

## 10. Comprobar lecturas reales y CSV

En **Ubuntu**, desde la carpeta del proyecto:

```bash
python3 scripts/verify_device.py --device UM1 --samples 3 --timeout 45
sudo docker compose exec db psql -U monitor -d monitor -c "SELECT d.device_code,r.temperature_c,r.humidity_percent,r.received_at FROM sensor_readings r JOIN devices d ON d.id=r.device_id WHERE d.device_code='UM1' ORDER BY r.id DESC LIMIT 5;"
sudo docker compose exec api python scripts/verify_csv.py
```

El primer comando espera tres recepciones nuevas sin generar datos. Para atribuirlas al sensor físico mantener apagado cualquier simulador; esperar a que se vacíe la cola del ESP32 para comprobar la medición actual. El dashboard debe mostrar recepción reciente y actualizar temperatura/humedad. Si la comparación CSV coincide con una inserción concurrente, desconectar brevemente el ESP32, esperar unos segundos y repetirla.

Para extraer el CSV desde el contenedor a Ubuntu:

```bash
mkdir -p ~/respaldos-iot
sudo docker compose cp api:/data/readings.csv "$HOME/respaldos-iot/readings.csv"
```

## 11. Dejar Ubuntu como servidor y probar persistencia

Una vez confirmadas las recepciones en Ubuntu, detener la instalación anterior de Windows desde **PowerShell**, sin borrar sus datos:

```powershell
Set-Location 'D:\UAO 2026\SEMESTRE 2\Iot IA\Taller 1'
docker compose stop
```

Comprobar otra recepción nueva en la IP de Ubuntu. Guardar evidencia de Ubuntu (`cat /etc/os-release`), contenedores (`sudo docker compose ps -a`), dashboard, consulta SQL y CSV.

Para probar persistencia, desconectar brevemente el ESP32 y anotar el conteo:

```bash
sudo docker compose exec db psql -U monitor -d monitor -c "SELECT count(*) FROM sensor_readings;"
sudo docker compose exec api python scripts/verify_csv.py
sudo docker compose restart db api
```

Esperar a que `curl --fail http://localhost:8000/health` responda correctamente, y repetir conteo y comparación. Deben conservarse. Volver a encender el ESP32.

Docker queda habilitado al arrancar Ubuntu y `db`/`api` tienen política `unless-stopped`. La VM debe estar encendida y el PC no debe suspenderse para recibir lecturas. Si se cambió la configuración o se detuvieron manualmente los servicios, ejecutar `sudo docker compose up -d`.

## Operación habitual y respaldo

Siempre dentro de `~/Actividad_1_IoT_IA`:

```bash
sudo docker compose ps -a
sudo docker compose logs --tail=80 api
sudo docker compose stop
sudo docker compose up -d
```

`stop` detiene la recepción; `up -d` la restablece. No ejecutar `docker compose down -v`: elimina los volúmenes con PostgreSQL y CSV.

Para respaldo lógico de PostgreSQL, sin eliminar nada:

```bash
mkdir -p ~/respaldos-iot
sudo docker compose exec -T db pg_dump -U monitor -d monitor -Fc > "$HOME/respaldos-iot/monitor-$(date +%Y%m%d-%H%M%S).dump"
```

Conservar también `.env` en un lugar privado. Descargar fuentes desde GitHub no restaura ni las mediciones ni los secretos.
