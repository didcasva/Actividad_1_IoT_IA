# AWS: captura, persistencia y observabilidad

La arquitectura académica separa aplicación, broker y Grafana en una EC2 de subred pública, y PostgreSQL e InfluxDB en una EC2 de subred privada. El despliegue y la captura física MQTT TLS se confirmaron el 24 de octubre de 2026; InfluxDB, Grafana y la alerta real de falta de datos se verificaron el 30 de octubre. La dirección elástica es `3.231.16.96`; las direcciones privadas son `192.168.0.200` (aplicación) y `192.168.1.142` (persistencia).

Usar las guías y Compose separados:

- [PostgreSQL e InfluxDB privados](../deploy/aws-db/README.md): volúmenes persistentes, enlaces a IP privada, rol SQL `monitor` sin permisos administrativos y tokens de InfluxDB por bucket.
- [Aplicación pública, HTTPS por IP y MQTT TLS](../deploy/aws-app/README.md): Caddy, API, migraciones, Mosquitto, receptor y perfil de Grafana; conexión a la persistencia externa.
- [Bitácora de la actividad 2](bitacora-aws-actividad2.md): qué se hizo, comandos, recursos, evidencias, persistencia y pendientes.
- [MQTT local](mqtt.md): entorno LAN y pruebas físicas anteriores. El Compose raíz no configura el despliegue público.

La instalación por IP utiliza certificados públicos de Let's Encrypt y Certbot, sin exigir un dominio. El timer renueva y recarga los certificados de ambos servicios. El dashboard y sus consultas requieren contraseña; el POST HTTPS conserva su API key. MQTT publica únicamente 8883 con TLS, usuarios separados y permisos por topic. El listener 1883 solo existe dentro de Docker; la API se enlaza al loopback del host. El enlace PostgreSQL usa la VPC y sus grupos de seguridad; no se configura TLS SQL en esta plantilla.

La configuración pública se probó primero localmente con PostgreSQL en otro proyecto Docker, una CA de pruebas y puertos de loopback. Posteriormente se confirmó el certificado público, el dashboard protegido, los servicios remotos saludables y la captura ESP32→AWS, con coincidencia SQL/CSV. El temporizador está activo y su primera ejecución automática terminó con código 0. No se forzó la sustitución de un certificado aún vigente ni se esperó su caducidad para ensayar la renovación real; los resultados y límites se registran en [validation.md](validation.md).

La extensión de la actividad 2 cargó el histórico en InfluxDB y verificó 2.951 coincidencias en SQL/CSV/InfluxDB. Tras apagar y reconectar el ESP32, se confirmaron 3.186 coincidencias SQL/InfluxDB, la alerta en `Firing`, el retorno a `Normal` y un aviso `Resolved` real en Discord. Ese canal es un complemento opcional de la implementación. Los conteos corresponden a cortes distintos.

Ambas EC2 tienen swap persistente de 1 GiB y Docker/containerd habilitados al inicio. Los siete servicios permanentes usan `unless-stopped`. La raíz pública se amplió sobre un volumen EBS de 15 GiB. La configuración se comprobó, pero el reinicio completo de ambas instancias queda pendiente de confirmar.

Para el ESP32, generar el archivo privado MQTT TLS y copiarlo al sketch cuando los servicios remotos estén saludables. Mantener Wi-Fi de 2.4 GHz con salida a Internet/NTP y validar CA e identidad del servidor. No utilizar `setInsecure()`. La ruta HTTP heredada del firmware utiliza HTTP para LAN; para el despliegue descrito se usa MQTT TLS. No apuntar ese transporte HTTP sin cifrar a Internet.

El rol `monitor` posee la BD para ejecutar migraciones. Una ampliación debe separar permisos de migración/ejecución, añadir límites de tasa y rotación de credenciales, y evaluar cobertura móvil, monitoreo y colas para interrupciones superiores a diez minutos. AWS IoT Core no forma parte de esta instalación; se utiliza Mosquitto en EC2.

## Respaldos y restauración

En la EC2 privada, desde la carpeta que contiene su Compose (por ejemplo `~/rutasalud-db`):

```bash
sudo docker exec rutasalud-db-db-1 pg_dump -U postgres -d monitor -w -Fc --verbose --lock-wait-timeout=10s -f /tmp/monitor.dump
sudo docker cp rutasalud-db-db-1:/tmp/monitor.dump ./monitor.dump
```

El respaldo guiado de la actividad 2 produjo un archivo de 54 KB con índice legible; no se probó su restauración. Copiar el respaldo fuera de la instancia y del repositorio, con almacenamiento cifrado y retención. Para ensayar una restauración sin modificar la BD original, crear otra base con el administrador (el rol `monitor` no puede crear bases):

```bash
sudo docker compose exec -T db createdb -U postgres -O monitor monitor_restore
sudo docker compose cp ./monitor.dump db:/tmp/monitor.dump
sudo docker compose exec -T db pg_restore -U postgres -d monitor_restore /tmp/monitor.dump
```

Comparar conteos y datos restaurados antes de cambiar cualquier `DATABASE_URL`. El CSV es una proyección recuperable de PostgreSQL; ejecutar reconciliación en la aplicación después de una restauración. Nunca usar `docker compose down -v` para actualizar una instalación con datos.
