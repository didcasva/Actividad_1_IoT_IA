# Wi-Fi y reinicios del ESP32-S3

## Diagnóstico del 20 de octubre de 2026

El registro comunicado termina en `Rebooting` y `rst:0xc (RTC_SW_CPU_RST)`. Eso describe el reinicio posterior al fallo, no identifica por sí solo una contraseña incorrecta, brownout o acceso nulo. Hace falta el encabezado del panic, incluido el núcleo y el tipo de error, y ambos backtraces si aparecen.

Se encontró en la caché de Arduino el ELF cuyo SHA256 empieza por `b58409665`, coincidente con el registro. Las direcciones del backtrace proporcionado resuelven a `esp_cpu_wait_for_intr`, `esp_vApplicationIdleHook`, `prvIdleTask` y `vPortTaskWrapper`. Es la tarea de reposo de FreeRTOS; este fragmento no demuestra un error en una línea concreta del sketch.

La compilación original usó `OLIMEX ESP32-S3-DevKit-Lipo` (`esp32s3-devkitlipo`) con flash configurada en 4 MB. Las fotos muestran una placa genérica ESP32-S3 N16R8. Corregir el perfil es necesario para reproducir las pruebas, pero no se ha demostrado que sea la causa del reinicio.

Después de liberar COM4 se capturaron dos reinicios con el encabezado **Interrupt wdt timeout on CPU1**. El backtrace de CPU1 resuelve a `DHT::expectPulse` (DHT.cpp:386), `DHT::read` (DHT.cpp:310), `DHT::readHumidity` y `loop` (línea 46 de la compilación original). La librería instalada era Adafruit DHT 1.4.7, con core Espressif 3.3.12. Ese registro localiza el bloqueo en la lectura DHT, no en la autenticación Wi-Fi. No permite determinar por sí solo si el sensor no responde por cableado, alimentación o avería.

Se reemplazó esa ruta por `BoundedDHT.h`, un lector local del protocolo DHT11/DHT22. Usa tiempo real en microsegundos, timeout por pulso de 120 us, espera inicial de 200 us, aborto en el primer timeout y un límite global de 8 ms para la sección crítica. La señal de inicio de 20 ms del DHT11 mantiene las interrupciones habilitadas. Un sensor sin respuesta devuelve una lectura inválida. No se desactiva ni amplía el watchdog, y se conserva la cola NVS.

## Perfil de prueba

Durante la carga, esptool identificó COM4 como **USB-Serial/JTAG nativo**, chip ESP32-S3 revision v0.2, PSRAM integrada de 8 MB. Para ese puerto seleccionar:

| Opción Arduino IDE | Valor |
|---|---|
| Placa | ESP32S3 Dev Module, paquete esp32 de Espressif Systems |
| Flash Size | 16MB (128Mb) |
| Flash Mode | QIO 80MHz |
| PSRAM | Disabled, para aislar el primer ensayo; este sketch no la necesita |
| USB Mode | Hardware CDC and JTAG |
| USB CDC On Boot | Enabled para salida Serial por el USB nativo de COM4 |
| Upload Speed | 115200 si hay errores de carga |
| Monitor serie | 115200 |

Si se cambia al conector rotulado COM, mediante puente USB-UART, usar USB CDC On Boot Disabled y seleccionar el puerto nuevo. No mezclar el puerto de monitorización con una compilación que envía Serial por la otra interfaz.

En Windows, se puede compilar el perfil USB nativo desde la raíz del proyecto:

```powershell
& 'C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe' compile --fqbn 'esp32:esp32:esp32s3:FlashSize=16M,PSRAM=disabled,USBMode=hwcdc,CDCOnBoot=cdc,FlashMode=qio' --build-path "$env:TEMP\iot-s3-cdc-build" firmware/esp32_dht_monitor
```

Los binarios contienen las credenciales de config.h; se generan fuera del repositorio y no se deben publicar.

## Qué observar

El firmware imprime `[BOOT] Reinicio=...`, modelo del chip, tamaño de flash, asociación Wi-Fi, asignación DHCP y `reason` de desconexión. No imprime SSID, contraseña ni API Key. Espera 30 s antes del reintento de respaldo; conserva AutoReconnect y las muestras pendientes, sin reiniciar por ausencia de Wi-Fi.

- `[WiFi] Asociado ... esperando IP`: hubo asociación; todavía falta DHCP.
- `[WiFi] Conectado. IP=...`: Wi-Fi y DHCP completados. Un POST fallido después requiere revisar servidor, firewall o API Key.
- `[WiFi] Desconexion. reason=...`: guardar el código y las líneas anteriores. No confundirlo con `WiFi.status()`.
- `Brownout detector ...` o motivo BROWNOUT: revisar cable/fuente/conexiones; no desactivar la protección.
- `Interrupt wdt`, `Task watchdog`, `Guru Meditation` o `assert failed`: guardar el encabezado completo y backtraces antes de regrabar para poder decodificarlos con el ELF correspondiente.

La red está confirmada por el usuario como 2.4 GHz. Si el dispositivo sigue reiniciándose, probar con el sensor desconectado y el ESP32 alimentado por un cable USB de datos fiable; mantener la misma configuración para aislar alimentación/cableado. No borrar NVS: contiene la cola de mediciones pendientes.

Referencias: [eventos Wi-Fi Arduino-ESP32](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html), [errores fatales ESP32-S3](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32s3/api-guides/fatal-errors.html).

## Resultado en hardware

La compilación del perfil USB nativo pasó con core 3.3.12 y ArduinoJson 7.4.3: 1 024 733 bytes de programa y 50 232 bytes de variables globales. Se cargó por COM4 con esptool 5.3.1 y verificación de hashes. No se borró NVS.

Después de un reinicio controlado de diagnóstico, se capturaron 45 segundos de ejecución con estos resultados:

```text
[BOOT] Chip=ESP32-S3, flash=16777216 bytes, PSRAM habilitada=0 bytes
[BOOT] Sensor=DHT11, GPIO=4
[WiFi] Asociado al punto de acceso; esperando IP por DHCP
[WiFi] Conectado. IP=192.168.20.146, RSSI=-32 dBm
[DHT] Lectura invalida: revisar DATA en GPIO4, alimentacion y GND
```

Se observaron cinco intentos de lectura inválida sin panic ni reinicio espontáneo en esa ventana. El reinicio reportado al comienzo (`Reinicio=11`) corresponde al reinicio USB solicitado para capturar el arranque. Esto verifica la conexión Wi-Fi y la recuperación frente a lecturas inválidas durante el ensayo; no demuestra estabilidad indefinida ni una lectura física válida del sensor.

La API local respondió 200 en /health, con host LAN 192.168.20.115. Todavía no se verificó ingestión HTTP desde el ESP32 porque el sensor no entrega una muestra válida. Pendiente revisar una foto del cableado actual, confirmando que el ESP-01S negro se haya retirado, que la señal del zócalo IO2 llegue a GPIO4, y que haya alimentación y tierra comunes.
