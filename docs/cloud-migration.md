# Segunda fase: AWS y MQTT

La arquitectura académica separa aplicación/broker en una EC2 de subred pública y PostgreSQL en una EC2 de subred privada. El usuario confirmó Docker en la pública, PostgreSQL saludable en la privada y autenticación SQL desde la pública. La dirección elástica es `3.231.16.96`; las direcciones privadas son `192.168.0.200` (aplicación) y `192.168.1.142` (BD).

Usar las guías y Compose separados:

- [PostgreSQL privado](../deploy/aws-db/README.md): volumen persistente, enlace a IP privada y rol `monitor` sin superusuario ni creación de roles/bases.
- [Aplicación pública, HTTPS por IP y MQTT TLS](../deploy/aws-app/README.md): Caddy, API, migraciones, Mosquitto y receptor; conexión a la BD externa.
- [MQTT local](mqtt.md): entorno LAN y pruebas físicas anteriores. El Compose raíz no configura el despliegue público.

La instalación por IP utiliza certificados públicos de Let's Encrypt y Certbot, sin exigir un dominio. El timer renueva y recarga los certificados de ambos servicios. El dashboard y sus consultas requieren contraseña; el POST HTTPS conserva su API key. MQTT publica únicamente 8883 con TLS, usuarios separados y permisos por topic. El listener 1883 solo existe dentro de Docker; la API se enlaza al loopback del host. El enlace PostgreSQL usa la VPC y sus grupos de seguridad; no se configura TLS SQL en esta plantilla.

La configuración pública se probó localmente con PostgreSQL en otro proyecto Docker, una CA de pruebas y puertos de loopback. Esto no demuestra despliegue AWS ni emisión ACME pública. La emisión remota, renovación ACME y captura ESP32→AWS deben comprobarse siguiendo la guía y registrando sus resultados en [validation.md](validation.md).

Para el ESP32, generar el archivo privado MQTT TLS y copiarlo al sketch cuando los servicios remotos estén saludables. Mantener Wi-Fi de 2.4 GHz con salida a Internet/NTP y validar CA e identidad del servidor. No utilizar `setInsecure()`. La ruta HTTP heredada del firmware utiliza HTTP para LAN; para el despliegue descrito se usa MQTT TLS. No apuntar ese transporte HTTP sin cifrar a Internet.

El rol `monitor` posee la BD para ejecutar migraciones. Una ampliación debe separar permisos de migración/ejecución, añadir límites de tasa y rotación de credenciales, y evaluar cobertura móvil, monitoreo y colas para interrupciones superiores a diez minutos. AWS IoT Core no forma parte de esta instalación; se utiliza Mosquitto en EC2.

## Respaldos y restauración

En la EC2 privada, desde la carpeta que contiene su Compose (por ejemplo `~/rutasalud-db`):

```bash
sudo docker compose exec -T db pg_dump -U postgres -d monitor -Fc -f /tmp/monitor.dump
sudo docker compose cp db:/tmp/monitor.dump ./monitor.dump
```

Copiar el respaldo fuera de la instancia y del repositorio, con almacenamiento cifrado y retención. Para ensayar una restauración sin modificar la BD original, crear otra base con el administrador (el rol `monitor` no puede crear bases):

```bash
sudo docker compose exec -T db createdb -U postgres -O monitor monitor_restore
sudo docker compose cp ./monitor.dump db:/tmp/monitor.dump
sudo docker compose exec -T db pg_restore -U postgres -d monitor_restore /tmp/monitor.dump
```

Comparar conteos y datos restaurados antes de cambiar cualquier `DATABASE_URL`. El CSV es una proyección recuperable de PostgreSQL; ejecutar reconciliación en la aplicación después de una restauración. Nunca usar `docker compose down -v` para actualizar una instalación con datos.
