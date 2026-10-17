# Segunda fase: VM Ubuntu

No se realiza despliegue público en esta fase. El mismo Compose se puede ejecutar en una VM Ubuntu de cualquier proveedor.

Antes de publicar: dominio y DNS hacia la VM; reverse proxy Caddy o Nginx con certificado HTTPS; publicar solo 80/443, enlazar api a 127.0.0.1:8000; SSH restringido. PostgreSQL permanece sin puerto publicado. Añadir autenticación de lectura/dashboard, límites de tasa y credenciales por dispositivo con rotación. La API actual comparte una clave y las consultas son públicas dentro de la LAN: no exponerla así a Internet.

Cambiar firmware a HTTPS con validación CA mediante WiFiClientSecure; nunca usar setInsecure. El sketch actual utiliza HTTP para la demostración LAN. Las claves viajan sin cifrado allí: utilizar red de laboratorio controlada y no reutilizar secretos de producción. Elegir conectividad del vehículo (router/hotspot con Internet) y evaluar períodos sin cobertura mayores a la capacidad de la cola.

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
