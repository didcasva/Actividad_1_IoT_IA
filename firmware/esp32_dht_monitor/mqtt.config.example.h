#pragma once
// Copiar a mqtt.config.h o generar con scripts/setup_mqtt.py.
// Al existir mqtt.config.h, el sketch usa MQTT en lugar de HTTP.
#define MQTT_HOST "192.168.1.100"
#define MQTT_PORT 1883
#define MQTT_USERNAME "device-UM1"
#define MQTT_PASSWORD "REEMPLAZAR_CON_CLAVE_LOCAL_DEL_DISPOSITIVO"
// DEVICE_CODE en config.h debe ser UM1 y existir en la base de datos.
#define MQTT_TLS 0 // Solo LAN. En nube activar TLS y configurar broker/certificados.
// Para TLS: MQTT_TLS=1, puerto del listener TLS y CA que valida su certificado.
// #define MQTT_CA_CERT R"PEM(-----BEGIN CERTIFICATE-----
// ...
// -----END CERTIFICATE-----
// )PEM"
