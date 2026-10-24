# ESP32 físico y DHT11

## Extensión MQTT

Para el nuevo requisito de broker/topics seguir [la guía MQTT](mqtt.md). Instalar **MQTT by Joel Gaehwiler (256dpi)** además de ArduinoJson 7 y generar el archivo privado `mqtt.config.h`. Su presencia selecciona MQTT; las instrucciones HTTP conservadas abajo aplican cuando ese archivo no existe. No cambia el cableado ni la estructura de la cola NVS. En MQTT la confirmación final del monitor serie es **guardado confirmado en PostgreSQL/CSV**.

## ESP32-S3 y placa ESP-01S DHT11 V1.0

El firmware actual usa `DHT_PIN 4` (GPIO4 / IO4 del ESP32-S3) y `DHT_TYPE DHT11`. El número de GPIO no es la posición física del pin en el conector.

La placa ESP-01S DHT11 V1.0 es un adaptador para un módulo ESP8266 ESP-01S. El [programa de referencia de IOT-MCU](https://github.com/IOT-MCU/ESP-01S-DHT11-v1.0) usa GPIO2 del ESP-01S para el sensor. Para utilizar solo su sensor desde el ESP32-S3, quitar el ESP-01S si estuviera insertado y usar la señal del contacto IO2 del zócalo como DATA hacia IO4 del ESP32-S3. Ese IO2 pertenece al zócalo ESP-01S: no implica cambiar DHT_PIN a 2.

Las fotos recibidas muestran ESP32-S3 N16R8 y una base azul TB:IOTMCU ESP-01S DHT11 V1.0 con el ESP-01S negro insertado. Desconectar alimentación y retirar ese módulo negro para utilizar el sensor con el ESP32-S3.

Conexión por el zócalo del ESP-01S:

| Contacto del zócalo ESP-01S | ESP32-S3 |
|---|---|
| VCC / 3V3 del zócalo | 3V3 |
| GND | GND |
| IO2, conectado a DATA del DHT11 | IO4 / GPIO4 |

Con la placa azul vista **por la cara de las soldaduras**, exactamente como la foto que muestra el texto `ESP-01S DHT11 v1.0 TB:IOTMCU` legible y las ocho soldaduras abajo, la huella ESP-01S corresponde a:

```text
        Texto ESP-01S DHT11 arriba

        RX     IO0    IO2    GND
        o       o      o      ■  ← pad cuadrado
        o       o      o      o
        VCC    RST    EN     TX

        Borde inferior de la placa
```

Así, DATA es la tercera soldadura de la fila superior contando desde la izquierda; GND es la superior derecha (cuadrada); VCC del zócalo es la inferior izquierda. Esta es una vista posterior: no trasladar izquierda/derecha sin reflejar al mirar el zócalo por delante. Confirmar continuidad sin alimentación antes de cablear, especialmente si se suelda directamente sobre la huella. [Pinout del fabricante ESP-01S, página 6 del PDF](https://www.laskakit.cz/user/related_files/1912111436_ai-thinker-esp-01s_c82893.pdf).

En el ESP32-S3, mirando el blindaje metálico de frente con la antena arriba y los USB abajo (foto frontal): 3V3 está en los dos primeros contactos de la izquierda; IO4 es el cuarto de esa misma fila, debajo de RST; GND está en el primer contacto de la derecha. Usar la serigrafía como referencia. La placa fotografiada no tiene tiras de pines soldadas: soldarlas o realizar una conexión soldada firme, sin dejar cables sueltos introducidos en los orificios.

No confundir VCC del zócalo de 3.3 V con el conector de entrada de la placa: algunas variantes incorporan regulador y su entrada requiere otra tensión. Confirmar serigrafía/esquema o continuidad sin alimentación antes de cablear. No alimentar el contacto VCC del ESP-01S ni los GPIO con 5 V. No insertar simultáneamente un ESP-01S que pueda controlar la misma línea de datos.

En Arduino IDE instalar `esp32 by Espressif Systems` en el gestor de placas; el paquete `Arduino ESP32 Boards` puede estar limitado a placas Arduino Nano ESP32 y no sustituye la selección de una placa ESP32-S3 genérica. Si no aparece el paquete, añadir en Preferencias → URLs adicionales del gestor de placas: `https://espressif.github.io/arduino-esp32/package_esp32_index.json`.

Seleccionar el modelo exacto o `ESP32S3 Dev Module` para una placa genérica compatible. Conservar Flash Size/PSRAM según el módulo real; no adivinar esos valores. Para USB nativo: `USB CDC On Boot: Enabled`, `Upload Mode: UART0 / Hardware CDC`. Si se conecta mediante puente USB-UART las opciones de USB nativo no aplican de la misma forma. [Referencia oficial de Espressif](https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/cdc_dfu_flash.html).

Instalar ArduinoJson 7. El lector DHT11/DHT22 está incluido en BoundedDHT.h y no requiere una biblioteca DHT externa. Abrir el sketch del proyecto y editar exclusivamente config.h para la configuración real. Verificar antes de subir. Si no conecta: mantener BOOT, pulsar y soltar RESET/EN, soltar BOOT, seleccionar el puerto que aparezca y subir; reiniciar después de la primera carga. Monitor serie a 115200. Para el fallo watchdog observado y el perfil exacto de prueba, ver [wifi-troubleshooting.md](wifi-troubleshooting.md).

El 17 de octubre se detectó COM3, pero esptool no recibió respuesta al identificar la placa. No se compiló ni grabó el firmware en esa comprobación. config.h local usa DEVICE_CODE UM1, registrado en la base local para evitar un 404. El ejemplo fue restaurado a valores ficticios; la configuración real se conservó en config.h, ignorado por Git.

Conectar con el equipo sin alimentación. Para el sensor DHT11 desnudo, mirando la rejilla de frente, verificar además el pinout del fabricante: pin 1 VCC a 3.3 V, pin 2 DATA a GPIO4, pin 3 sin conectar, pin 4 GND a GND. Pull-up 4.7–10 kΩ entre DATA y 3.3 V si no está integrada. En módulos de tres pines seguir las etiquetas VCC/DATA/GND: su orden puede variar. No aplicar 5 V al GPIO del ESP32.

1. Arduino IDE: instalar la plataforma **esp32 by Espressif Systems** y seleccionar el modelo real de placa y su puerto COM.
2. Instalar **ArduinoJson 7**. El lector DHT con tiempos de espera acotados está incluido en el proyecto.
3. Copiar `config.example.h` como `config.h` junto al sketch. Este archivo está ignorado por Git.
4. Configurar SSID y clave del Wi-Fi/hotspot 2.4 GHz. PC servidor y ESP32 deben poder comunicarse; algunas redes de invitados aíslan clientes.
5. Configurar API_URL con la IP LAN del PC (`ipconfig` en Windows, `hostname -I` en Ubuntu), puerto 8000 y ruta /api/v1/readings. Desde el ESP32 localhost apunta al propio ESP32.
6. Copiar API_KEY del .env local; DEVICE_CODE debe existir en devices. Predeterminado esp32-01. DHT_TYPE predeterminado DHT11; permite DHT22, con actualización correspondiente en la BD.
7. Abrir esp32_dht_monitor.ino, compilar, cargar y abrir Serial a 115200 baudios.
8. Verificar HTTP 200 cada ~10 s, dashboard y conteos SQL/CSV.

La sincronización NTP no bloquea el inicio. Si todavía no hay fecha válida, se transmite null y el servidor usa recepción, también para muestras almacenadas sin reloj. Con NTP disponible la muestra conserva su hora UTC durante desconexiones.

Copiar configuración desde PowerShell:

```powershell
Copy-Item firmware/esp32_dht_monitor/config.example.h firmware/esp32_dht_monitor/config.h
ipconfig
```

En Ubuntu:

```sh
cp firmware/esp32_dht_monitor/config.example.h firmware/esp32_dht_monitor/config.h
hostname -I
```

Prueba física pendiente: comparar una medición con un instrumento de referencia; desconectar Wi-Fi dos minutos; restablecerlo; comprobar vaciado de cola y ausencia de duplicados. Apagar/reencender ESP32 con muestras pendientes y comprobar recuperación NVS. Evaluar ubicación lejos de sol directo, salidas del aire acondicionado y fuentes de calor. La vibración, alimentación y cobertura del vehículo requieren pruebas reales.

La cola persiste tras reinicio. Cambiar DEVICE_CODE con una cola pendiente reasigna esas muestras al nuevo código: vaciarla antes de cambiar de unidad. No cambiar el formato de la estructura sin migrar/versionar la cola.

Actualización del 20 de octubre: se compiló y cargó el firmware en el ESP32-S3 físico, se verificó conexión Wi-Fi y se observó ejecución durante 45 s sin el panic anterior. En un ensayo posterior se confirmó lectura válida de 27.1 °C / 72 %RH por COM4, POST 200, recepción de tres nuevas muestras consecutivas, almacenamiento coincidente en PostgreSQL/CSV y visualización de UM1 en el dashboard. Ver [diagnóstico](wifi-troubleshooting.md) y [captura del dispositivo real](real-device.md).
