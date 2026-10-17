#pragma once
#define WIFI_SSID "SU_RED_2_4_GHZ"
#define WIFI_PASSWORD "SU_CLAVE"
// IP LAN del PC o servidor; nunca localhost desde el ESP32.
#define API_URL "http://192.168.1.100:8000/api/v1/readings"
#define API_KEY "MISMA_CLAVE_DEL_ENV"
#define DEVICE_CODE "esp32-01"
#define DHT_PIN 4
#define DHT_TYPE DHT11 // Cambiar a DHT22 y actualizar devices.sensor_type.
