# Segunda fase: AWS y MQTT

La integración MQTT local está descrita en [mqtt.md](mqtt.md). No se ha realizado un despliegue público en AWS. El Compose actual sirve para la LAN; el requisito académico de aplicación en subred pública y base de datos en subred privada requiere separar los servicios entre hosts de AWS.

Diseño propuesto: EC2 Ubuntu en subred pública con IP elástica, reverse proxy HTTPS, API/dashboard, receptor MQTT y broker Mosquitto con TLS; PostgreSQL en una EC2 de subred privada sin IP pública. El grupo de seguridad de la BD autoriza 5432 solamente desde el grupo de la aplicación. Configurar `DATABASE_URL` con el DNS/IP privado de la BD y un rol SQL propio. En ese despliegue no iniciar el servicio `db` local del Compose; preparar archivos Compose separados y ejecutar las migraciones contra la BD privada. Esta configuración AWS todavía está pendiente.

Mosquitto necesita listener MQTT TLS, certificados válidos y restricciones por topic como las del laboratorio. En el firmware activar `MQTT_TLS=1`, configurar `MQTT_CA_CERT` y el puerto TLS; la ruta de código existe pero no ha sido ensayada con un broker TLS. El receptor usa TCP sin TLS dentro de la red Docker local; una conexión a un broker externo requiere adaptar también su cliente/configuración TLS. AWS IoT Core puede sustituir al broker propio si se elige ese servicio; no se han creado recursos ni certificados de IoT Core.

Antes de publicar: dominio y DNS hacia la VM; reverse proxy Caddy o Nginx con certificado HTTPS; publicar 80/443 para web y 8883 para MQTT TLS con acceso controlado, enlazar api a 127.0.0.1:8000; SSH restringido. No publicar MQTT 1883. En el host privado, publicar PostgreSQL únicamente sobre su IP privada para los servicios autorizados por el grupo de seguridad. Añadir autenticación de lectura/dashboard, límites de tasa y credenciales por dispositivo con rotación. La API actual comparte una clave y las consultas son públicas dentro de la LAN: no exponerla así a Internet.

Para la ruta HTTP heredada, cambiar firmware a HTTPS con validación CA mediante WiFiClientSecure; nunca usar setInsecure. HTTP y el listener MQTT 1883 actuales son para la LAN de laboratorio: sus credenciales viajan sin cifrar. Elegir conectividad del vehículo (router/hotspot con Internet) y evaluar períodos sin cobertura mayores a la capacidad de la cola.

Inyectar DATABASE_URL/API_KEY mediante variables o gestor de secretos, con permisos restringidos para .env. Separar credencial de migración y rol de aplicación, minimizar permisos SQL. Ejecutar migraciones antes de iniciar nuevas versiones. Establecer backups, retención, monitorización y pruebas de restauración. El CSV sigue siendo una proyección recuperable de la BD.

Backup dentro del contenedor para evitar corrupción por redirección binaria de PowerShell antiguo:

```sh
docker compose exec db pg_dump -U monitor -d monitor -Fc -f /tmp/monitor.dump
docker compose cp db:/tmp/monitor.dump ./monitor.dump
```

Restaurar en una base nueva, sin destruir la original:

```sh
docker compose exec db createdb -U monitor monitor_restore
docker compose cp ./monitor.dump db:/tmp/monitor.dump
docker compose exec db pg_restore -U monitor -d monitor_restore /tmp/monitor.dump
```

Validar conteos en monitor_restore antes de cambiar DATABASE_URL. Reconstruir CSV después de restaurar. Guardar backups fuera de la VM y del repositorio, cifrados, con una política de retención y recuperación ensayada.
