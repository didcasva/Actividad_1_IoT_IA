# Validación y evidencias

Registro cronológico: los límites de cada ensayo describen lo que se comprobó en ese momento. La actualización más reciente es [Actividad 2 en AWS](#actividad-2-en-aws), con salidas SSH, capturas y confirmaciones del usuario durante el despliegue guiado del 30 de octubre de 2026. Para exponer los resultados, consultar el [guion](guia-presentacion-actividad2.md); para repetir la operación, la [bitácora técnica](bitacora-aws-actividad2.md).

## Pruebas iniciales — 17 de octubre de 2026

Caso de uso confirmado: unidades móviles de salud. Hardware disponible según el usuario: ESP32 y DHT11. DHT22 se conserva como alternativa configurable.

| Verificación ejecutada | Resultado |
|---|---|
| Python local 3.12.14 + pytest (SQLite temporal) | 15 pasaron, 1 advertencia de deprecación TestClient/httpx |
| pytest dentro de contenedor con PostgreSQL 16, base monitor_test | 15 pasaron en 1.07 s, misma advertencia |
| docker compose config --quiet | Correcto |
| docker compose up -d --build | Imágenes construidas; migraciones completadas; API y PostgreSQL iniciados |
| Alembic current | 002 (head), dispositivo demo DHT11 |
| Simulador real HTTP | 5 solicitudes, 5 respuestas 200 |
| SQL y CSV físico | Coincidencia exacta de las 5 mediciones |
| docker compose restart db api | Conteo SQL conservado en 5; CSV coincide; /health devuelve ok |
| Reconciliación tras corrupción del CSV | Cubierta por pytest |
| Fallo de CSV después del commit SQL y reintento | Cubierto por pytest: 503 inicial, 200 después, una sola fila |
| Reintentos concurrentes | 8 solicitudes con igual identidad, una sola fila |
| node --check frontend/static/app.js | Correcto |
| Dashboard en navegador | Tarjetas, tablas y ambas gráficas visibles con las 5 muestras; indicador de falta de recepción reciente visible |

La primera ejecución de pruebas PostgreSQL usó una URL sin contraseña y falló en la conexión. Se corrigió utilizando DATABASE_URL del entorno del contenedor y la suite completa pasó. La revisión inicial del navegador detectó un error de sintaxis JS, corregido antes de la verificación visual final. Chart.js se incluyó localmente para permitir funcionamiento sin Internet.

Los tests validan salud HTTP, límites, JSON malformado, autenticación, inserción, idempotencia, consultas, exportación CSV, reconstrucción y recuperación ante fallo de archivo. La persistencia tras reinicio de contenedores se verificó como prueba de integración manual con datos simulados.

No ejecutado: compilación Arduino, carga por USB, lectura física DHT11, reconexión Wi-Fi real, recuperación NVS en ESP32, ensayo en vehículo, instalación en Ubuntu y despliegue HTTPS. No se afirma que estas pruebas hayan pasado. No hubo despliegue en nube ni commit/push.

Los datos presentes en PostgreSQL son sintéticos; no provienen del sensor físico. No interpretar sus valores como condiciones reales de una unidad móvil. Las advertencias TestClient/httpx no impiden las pruebas, pero conviene migrar el cliente de pruebas cuando se actualice el stack.

Para repetir instalación, pruebas y simulación, ver README y local-deployment.md. La suite PostgreSQL borra tablas solo en la base dedicada monitor_test; no ejecutarla contra monitor.

## Actualización física — 20 de octubre de 2026

Se decodificó el ELF exacto del panic original y se localizó un Interrupt WDT en la lectura DHT de Adafruit. Se sustituyó esa lectura por BoundedDHT.h, con tiempos reales y aborto inmediato al primer timeout, y se añadió diagnóstico Wi-Fi/reset.

Compilación para ESP32S3 Dev Module, flash 16 MB, PSRAM deshabilitada y USB CDC habilitado: correcta. Carga física por COM4: correcta, con hashes verificados. Captura posterior de 45 s: Wi-Fi asociado y con IP 192.168.20.146, RSSI -32 dBm, cinco lecturas DHT inválidas y ningún nuevo panic/reinicio espontáneo. La API local respondió 200 en /health.

Pendiente: obtener lecturas físicas válidas del DHT11, ingestión HTTP desde este ESP32, reconexión real al interrumpir Wi-Fi y ensayo prolongado de estabilidad. Los datos históricos de pruebas simuladas no demuestran esos puntos. Detalles y perfil de compilación en wifi-troubleshooting.md.

### Ensayo posterior: captura física confirmada

Se observaron por COM4 lecturas de 27.1 °C / 72 %RH y respuestas POST 200. scripts/verify_device.py, que solo consulta la API y no genera datos, confirmó tres muestras nuevas consecutivas de UM1: IDs 383, 384 y 385 a intervalos de unos 10 s. El dashboard se comprobó en navegador con UM1 seleccionada, tarjetas y estado de recepción activa. También se verificó el estado sin recepción reciente antes de reconectar el dispositivo.

PostgreSQL y CSV coincidieron exactamente en 389 filas en la comprobación final. node --check frontend/static/app.js y git diff --check pasaron. Se reconstruyó y arrancó la API con los cambios del dashboard. No se volvió a ejecutar la suite backend porque este cambio no altera su lógica; los resultados pytest anteriores siguen documentados en su ensayo original.

Esto completa la verificación física de lectura, ingestión y visualización que estaba pendiente en el ensayo anterior. Siguen pendientes la interrupción controlada de Wi-Fi con recuperación NVS, la estabilidad prolongada, las pruebas en vehículo y Ubuntu.

## Extensión MQTT — 24 de octubre de 2026

Se incorporaron Mosquitto y receptor Python mediante el perfil Compose `mqtt`. Pruebas backend con PostgreSQL en base independiente: **29 pasaron** en 2.81 s; una advertencia de deprecación de TestClient/httpx. Incluyen idempotencia HTTP/MQTT, discrepancia topic/dispositivo, JSON/rangos inválidos y ausencia de ACK de guardado cuando falla CSV después del commit SQL.

En el proyecto aislado `taller1-mqtt-test`, con puertos 18000/18884 y volúmenes propios, se publicaron mensajes sintéticos de UM1. Se comprobó recepción MQTT real en Mosquitto, acuse `stored`, una sola fila PostgreSQL/CSV al repetir, rechazo de publicación en otra unidad y rechazo de JSON/identidad inválidos. También se comprobaron rechazo de ACK falsificado por el usuario del dispositivo y conexiones anónimas/con contraseña incorrecta. Estos mensajes no provienen del sensor.

Con el receptor detenido se publicó otra muestra, se reinició el broker conservando su volumen y se inició el receptor: se recuperó exactamente una fila, sin necesidad de republicar. También se ensayó publicar con PostgreSQL detenido en el entorno aislado y verificar su recuperación al restablecerlo. El ensayo de fallos de servidor no equivale a interrumpir físicamente el Wi-Fi del ESP32.

Antes de activar MQTT en el proyecto principal se respaldaron PostgreSQL y CSV en `.backups/mqtt-upgrade-20261024`. Se preservaron **1543 mediciones** y la comparación exacta SQL/CSV. Ningún mensaje de los ensayos MQTT aislados fue insertado en ese histórico. API, DB, broker y receptor quedaron saludables.

El sketch MQTT compiló para `esp32:esp32:esp32s3`, core 3.3.12, flash 16 MB, PSRAM deshabilitada, USB CDC habilitado, ArduinoJson 7 y MQTT 2.5.3: 929965 bytes de programa (70 %) y 50168 bytes globales (15 %). También compiló la variante HTTP sin `mqtt.config.h`: 1024789 bytes (78 %) y 50232 bytes globales (15 %).

Después de conectar el ESP32 por USB se cargó la versión MQTT por COM4, con hashes de flash verificados. Se observaron por Serial lecturas DHT11 válidas, publicaciones aceptadas por broker y confirmaciones de guardado con cola en cero. Tres nuevas mediciones de UM1, IDs 1563, 1564 y 1565, fueron recibidas a las 08:53:16, 08:53:26 y 08:53:36 (America/Bogota), con 28.9/29.0 °C y 70 %RH. Las secuencias 4, 5 y 6 aparecen en los logs de `mqtt-worker` con esas mismas IDs, lo que vincula la consulta HTTP de observación con la ingestión MQTT real.

Los registros serie locales están en `.backups/mqtt-upgrade-20261024`, fuera de Git. Abrir la conexión USB para observar puede provocar un reinicio USB controlado (motivo 11); no se atribuye a un panic espontáneo. No se han validado TLS, AWS, estabilidad prolongada ni cobertura en vehículo.

Se interrumpió el broker durante aproximadamente 20 s con el ESP32 físico encendido. Al restablecerlo se observaron reconexión, hasta tres muestras pendientes y descenso de la cola a cero únicamente tras acuses de aplicación. Las secuencias 18, 19 y 20 quedaron con IDs 1577, 1578 y 1579; el reintento de la secuencia 18 reutilizó ID 1577. Consulta de grupos duplicados por unidad/boot/secuencia: cero. Comparación al cierre de ese ensayo: **1585 filas PostgreSQL/CSV coincidentes**, incluyendo nuevas mediciones físicas y conservando las anteriores. Esta prueba cubre interrupción MQTT, no apagado del ESP32 con cola ni pérdida real de Wi-Fi.

## Plantilla de PostgreSQL privado AWS — 24 de octubre de 2026

Se preparó `deploy/aws-db` para publicar PostgreSQL 16 sobre la IP privada configurada y conservar los datos en volumen. Prueba local independiente `taller1-aws-db-test`, enlazada solo a 127.0.0.1:15432: contenedor saludable, autenticación TCP de `monitor`, migraciones Alembic hasta 002 y rechazo de creación de bases/roles. El usuario `monitor` no es superusuario. El entorno de prueba se detuvo al terminar, conservando su volumen y sin utilizar las mediciones del proyecto principal.

El usuario confirmó SSH a la EC2 privada 192.168.1.142 y HTTP 200 al repositorio de Docker. Posteriormente compartió la ejecución remota de Compose: `rutasalud-db-db-1` saludable, volumen `rutasalud-db_postgres_data` creado y puerto publicado solo sobre `192.168.1.142:5432`. La consulta de catálogo devolvió propietario `monitor` y los permisos `rolsuper`, `rolcreatedb` y `rolcreaterole` en `f`. Una captura de EC2 confirma IP elástica `3.231.16.96` e IP privada `192.168.0.200` para el servidor público. Estas son evidencias aportadas por el usuario. Posteriormente confirmó que la autenticación TCP a PostgreSQL desde el público funcionó; el despliegue de la aplicación sigue pendiente. Los secretos de la prueba local permanecen en `.backups`, excluidos de Git.

## Aplicación AWS con HTTPS por IP y MQTT TLS — 24 de octubre de 2026

Se preparó `deploy/aws-app` separado del Compose LAN, conectado a PostgreSQL externo: migraciones, API enlazada al loopback, CSV compartido, receptor, Mosquitto con listener público TLS y Caddy con contraseña para dashboard/consultas. `setup_aws_app.py` genera credenciales AWS propias, hash bcrypt, ACL, raíces CA y un archivo de firmware separado. Los scripts no reemplazan la configuración LAN ni cargan automáticamente el ESP32.

Pruebas locales en el proyecto Docker independiente `rutasalud-app`, con IP 127.0.0.1, puertos 18080/18443/18885/18001, CA exclusiva de pruebas y base `taller1-aws-db-test`: servicios saludables y migración contra el host externo. Registro idempotente de UM1. HTTPS exige contraseña; login correcto entrega dashboard, credencial incorrecta devuelve 401 y GET sin login devuelve 401. POST sin API key devuelve 401; con clave válida inserta y el reintento conserva la misma ID. Un cliente sin la CA de prueba rechaza el certificado.

Cliente MQTT Paho con validación CA/IP: conexión TLS, credencial de UM1, publicación QoS 1 y ACK `stored`; una identidad de servidor incorrecta fue rechazada. Las mediciones sintéticas HTTP/MQTT se guardaron solo en esta base aislada: cuatro filas al finalizar dos ensayos, con coincidencia exacta PostgreSQL/CSV. No se insertaron datos de estas pruebas en el histórico LAN.

Se probó `sync` dentro de Linux con un volumen TLS propio: rechazo de certificado para otra IP, conservación del certificado activo anterior y activación atómica del par correcto. Tras `caddy reload --force` y SIGHUP del broker, ambos servicios aceptaron conexiones verificadas con el nuevo certificado. Certbot Docker reportó 5.8.0. No se solicitaron certificados ACME reales ni de staging durante las pruebas locales; la emisión y renovación ACME remotas y la activación del timer en Ubuntu siguen pendientes.

La variante MQTT TLS compiló con ESP32-S3/core 3.3.12, flash 16 MB, PSRAM deshabilitada y USB CDC habilitado: 1019261 bytes de programa (77 %) y 50704 bytes globales (15 %). Se usó una copia privada del sketch; no se cargó este firmware AWS al ESP32 físico. La captura física en AWS queda pendiente de desplegar los servicios remotos y cambiar el archivo MQTT del dispositivo. Los contenedores de prueba se detuvieron conservando sus volúmenes; el proyecto LAN se preservó.

## Captura física en AWS — 24 de octubre de 2026

El usuario aportó la emisión ACME exitosa del certificado público para `3.231.16.96`, con vencimiento el 31 de octubre de 2026, y el estado remoto de API/broker/receptor saludables. Confirmó acceso al dashboard con contraseña y agregó la regla MQTT. Desde el PC se comprobó HTTPS con validación de certificado (401 sin credencial, como corresponde) y el listener 8883 con TLS/cadena/IP válidas. La consulta remota `/health` devolvió `status`, `database` y `csv` en `ok`. El acceso visual autenticado al dashboard fue confirmado por el usuario; la pestaña no estuvo disponible para inspección automatizada durante este ensayo.

Se descargó por SFTP el archivo privado MQTT generado en AWS, se conservó copia de la configuración LAN y se cambió únicamente el `mqtt.config.h` privado del sketch a IP elástica, puerto 8883, usuario de UM1, TLS y raíces ISRG. No se incluyeron claves en Git ni en la salida de herramientas. Compilación de producción con core 3.3.12: 1020925 bytes de programa (77 %), 50704 bytes globales (15 %). Carga física a ESP32-S3 MAC `7c:0c:5f:5b:14:fc` por COM4, con hashes de flash verificados y conservando NVS.

Antes de la carga, la API AWS no tenía lecturas para UM1. Tras cargar se observaron DHT11 válido, publicación MQTT y confirmación de guardado con cola en cero. Un observador MQTT autenticado y sin publicaciones de prueba recibió seis ACK `stored`, secuencias 0–5 e IDs 1–6. `verify_device.py` ejecutado por SSH en la EC2 pública confirmó tres lecturas nuevas consecutivas: IDs 3, 4 y 5, recibidas a las 13:59:42, 13:59:52 y 14:00:02 America/Bogota, con 29.3 °C y 65 %RH. Los logs del receptor vinculan esas mismas IDs y secuencias con ingestión MQTT. Se observó posteriormente 28.9 °C / 65 %RH por Serial.

Comprobación remota `verify_csv.py`: siete mediciones PostgreSQL/CSV exactamente coincidentes en ese instante; el sensor siguió enviando después. No se utilizó simulador ni se publicaron muestras sintéticas en la base AWS. El histórico LAN se conservó en su entorno independiente. Los registros de Serial y ACK están en `.backups/aws-migration`, fuera del repositorio.

Se consultó systemd por SSH: timer `rutasalud-cert-renew.timer` activo; servicio de renovación con `Result=success`, `ExecMainStatus=0` y primera ejecución a las 18:55:55 UTC (13:55:55 America/Bogota). Esto confirma la ejecución programada de comprobación/recarga. No se forzó la renovación de un certificado todavía vigente ni se validó su sustitución tras días de operación. Siguen pendientes estabilidad prolongada, pérdida real de Wi-Fi, apagado con cola y ensayo en vehículo; las pruebas locales de recarga no sustituyen esos ensayos.

## InfluxDB — 30 de octubre de 2026

Se integró InfluxDB como proyección de series de tiempo en la ingestión común de HTTP y MQTT, con carga del histórico y comparación contra PostgreSQL. La suite backend pasó completa: **40 pruebas** con SQLite, 11 de ellas nuevas. Cubren el formato de los puntos, el reintento sin NTP, la ausencia de ACK mientras InfluxDB falla, la recuperación sin duplicar filas y `/health`. Las respuestas de InfluxDB están simuladas en esas pruebas.

También se ejecutó el código contra un `influxd` 2.7.11 real para Windows, en loopback y con datos descartables, usando SQLite y un token limitado al bucket creado por la API. Pasaron 16 comprobaciones: escritura y consulta Flux reales, coincidencia exacta con la base, reintento sin NTP y `reconcile_influx.py` repetido sin puntos adicionales (conteo real de puntos), detección de mediciones faltantes y distintas por `verify_influx.py`, y 503 con recuperación posterior ante InfluxDB caído o token inválido. Los mensajes fueron sintéticos y no pasaron por Mosquitto.

No ejecutado en ese ensayo: la imagen `influxdb:2.7-alpine`, Compose y PostgreSQL junto a InfluxDB; se cubrieron en el ensayo siguiente.

## Grafana y stack completo en Docker — 30 de octubre de 2026

Se levantó en Docker Desktop el proyecto aislado `rutasalud-e2e` con `compose.yaml`: PostgreSQL, migraciones, API, Mosquitto, receptor, `influxdb:2.7-alpine` y `grafana/grafana:13.2.5`. Un archivo de prueba agregó un webhook local en lugar de Discord, y Caddy con el `Caddyfile` de AWS y un certificado autofirmado. Grafana usó la misma configuración `/grafana` de AWS. Los tokens se crearon con los comandos `influx bucket list` e `influx auth create` de la guía; Grafana usó el de solo lectura.

Un cliente Paho publicó como `device-UM1` por MQTT real, con datos sintéticos cada 10 s. **45 publicaciones, 45 ACK `stored`** y coincidencia exacta de 45 mediciones en PostgreSQL/CSV (`verify_csv.py`) y PostgreSQL/InfluxDB (`verify_influx.py`). Se comprobaron la fuente de datos, el dashboard en navegador, las tres reglas y el punto de contacto. Por Caddy, `/grafana/` respondió 200 y `/` exigió contraseña (401).

| Alerta | Condición de prueba | Disparo | Resolución | Webhook |
| --- | --- | --- | --- | --- |
| Temperatura | 35 °C | 95 s | 35 s | Disparo y resolución recibidos |
| Humedad | 90 % | 95 s | 35 s | Disparo y resolución recibidos |
| Sin mediciones | Publicador detenido | 221 s | 35 s | Disparo y resolución recibidos |

El ensayo encontró un defecto corregido: `$$labels` no se convierte en `$` en las anotaciones y dejaba las alertas sin mensaje. Después de la prueba se ajustó la redacción de los mensajes, sin cambiar la lógica. La salida de la nueva redacción no se volvió a ejecutar.

No ejecutado en ese ensayo local: entrega real a Discord (el webhook fue local con el formato de Discord), `deploy/aws-app/compose.yaml` y `deploy/aws-db/compose.yaml` completos, certificado público, despliegue en AWS, memoria disponible en las EC2 y lecturas del sensor físico. Esos puntos se distinguen de la verificación guiada de AWS registrada a continuación.

## Actividad 2 en AWS

**Fecha de corte:** 30 de octubre de 2026, hora de Colombia. Las salidas posteriores a medianoche UTC del 31 corresponden todavía al día 30 en `America/Bogota`.

El usuario ejecutó los comandos remotos y compartió sus resultados y capturas. Se contrastaron con el código del commit `4973629`. No se presenta esta sesión como una inspección SSH automatizada realizada por el asistente. La consigna original de la actividad 2 no estaba disponible; Discord se registra como canal opcional elegido en la implementación.

| Verificación | Evidencia y resultado |
| --- | --- |
| Revisión local del código integrado | 40 pruebas backend aprobadas con SQLite temporal; ambos Compose de AWS válidos con valores ficticios. Una advertencia de deprecación TestClient/httpx. |
| Respaldo de PostgreSQL privado | Dump CUSTOM de 54 KB copiado al host, permisos 600 e índice de 27 entradas legible. Restauración completa no ejecutada. |
| InfluxDB privado | `rutasalud-db-influxdb-1` saludable, `influx ping` devuelve `OK`, publicación en `192.168.1.142:8086`. |
| Acceso desde la pública | `/health` de InfluxDB responde `pass`, versión `v2.7.12`. |
| Conexión de API y receptor | Contenedores actualizados saludables; API devuelve `status`, `database`, `csv` e `influx` en `ok`. |
| Carga del histórico | `reconcile_influx.py`: 2.951 mediciones. |
| Consistencia inicial | `verify_influx.py`: 2.951 coincidentes, cero puntos adicionales. `verify_csv.py`: 2.951 coincidentes. |
| Recepción física inicial | IDs 2953–2955, 28,9 °C y 65 %, recibidas aproximadamente cada diez segundos. |
| Ampliación de disco | Después de descargar Grafana quedaban 259 MiB libres (97 %). EBS público ampliado a 15 GiB; partición raíz de 13,9 GiB, ext4 de unos 14 GiB y 7,1 GiB libres tras la ampliación. |
| Grafana y HTTPS | `rutasalud-app-grafana-1` saludable; `https://3.231.16.96/grafana/api/health` devuelve `database: ok`, versión 13.2.5. |
| Dashboard y reglas | [Captura](evidencias/actividad2-aws-reglas-normal.png) con las tres reglas aprovisionadas en `Normal`; el usuario confirmó gráficas con datos recientes. |
| Alerta real de ausencia de datos | Captura de Discord con `Firing`, `Sin mediciones de UM1` y `grafana_state_reason = NoData`, después de apagar el ESP32. |
| Recuperación física | IDs 3184–3186, 27,6 °C y 68 %, recibidas a las 23:16:26, 23:16:36 y 23:16:46 de Colombia. |
| Consistencia posterior | 3.186 mediciones coincidentes entre SQL e InfluxDB, cero puntos adicionales. No se aportó una nueva comparación CSV de ese corte. |
| Resolución de la alerta | El usuario confirmó retorno a `Normal`, recepción de `Resolved` y actualización de las gráficas. |
| Inicio de Docker | Docker y containerd `enabled` en las dos EC2. |
| Políticas de contenedores | Cinco servicios públicos y dos privados con `unless-stopped`. |
| Swap | 1 GiB activo en cada EC2 y entrada de `/swapfile-rutasalud` presente en ambos `/etc/fstab`. |
| Certificados | Temporizador `rutasalud-cert-renew.timer` confirmado como `enabled` y `active` en la pública. |

Los conteos son instantáneas de un histórico que continuó creciendo. Las comparaciones CSV y SQL/InfluxDB no se extrapolan a otros cortes. Los intervalos de disparo y resolución en AWS no se cronometraron; las duraciones de 95 s y 221 s del apartado anterior pertenecen exclusivamente al ensayo local sintético.

**Pendiente de confirmar:** reinicio completo de ambas EC2 y recuperación sin `compose up`, restauración del dump, respaldo fuera de las instancias, identificación de la instantánea EBS si se creó, disparo físico de los umbrales de temperatura/humedad en AWS, recuperación de cola durante una pérdida real de Wi-Fi y estabilidad prolongada. No se forzó una nueva renovación ACME en esta sesión.

Los detalles de recursos, credenciales por función, comandos y procedimientos pendientes están en la [bitácora técnica](bitacora-aws-actividad2.md).
