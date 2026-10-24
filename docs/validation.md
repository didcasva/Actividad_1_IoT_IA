# Validación real — 17 de octubre de 2026

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
