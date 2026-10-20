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
