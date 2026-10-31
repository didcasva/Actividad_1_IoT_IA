#include <WiFi.h>
#include <HTTPClient.h>
#include "BoundedDHT.h"
#include <ArduinoJson.h>
#include <Preferences.h>
#include <esp_system.h>
#include <time.h>
#include "config.h"
#if __has_include("http.config.h")
#include "http.config.h" // Configuracion AWS: reemplaza API_URL y API_KEY de config.h.
#endif

#ifdef API_CA_CERT
#include <WiFiClientSecure.h>
WiFiClientSecure apiNetwork;
#endif

BoundedDHT dht(DHT_PIN, DHT_TYPE);
Preferences prefs;
// Cola persistente: 60 muestras = 10 minutos. Al llenarse se descarta
// explícitamente la muestra nueva; las pendientes mantienen su identidad.
struct Sample { float t, h; uint64_t epoch; uint32_t seq; char boot[33]; };
struct Queue { uint32_t version; uint32_t count; Sample items[60]; } queueData;
char bootId[33];
uint32_t sequenceNumber=0, nextRead=0, nextSend=0, nextWifi=0, backoff=1000;
bool due(uint32_t now, uint32_t deadline) { return (int32_t)(now-deadline)>=0; }
const char* resetName(esp_reset_reason_t reason) {
  switch(reason) {
    case ESP_RST_POWERON: return "encendido";
    case ESP_RST_EXT: return "reset externo";
    case ESP_RST_SW: return "reinicio por software";
    case ESP_RST_PANIC: return "panic / excepcion (revisar encabezado del error)";
    case ESP_RST_INT_WDT: return "watchdog de interrupciones";
    case ESP_RST_TASK_WDT: return "watchdog de tareas";
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_BROWNOUT: return "brownout / caida de alimentacion";
    default: return "otro";
  }
}
void onWiFiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  // No conectar/desconectar desde este callback: se ejecuta en otra tarea.
  if(event==ARDUINO_EVENT_WIFI_STA_CONNECTED) {
    Serial.println("[WiFi] Asociado al punto de acceso; esperando IP por DHCP");
  } else if(event==ARDUINO_EVENT_WIFI_STA_GOT_IP) {
    Serial.printf("[WiFi] Conectado. IP=%s, RSSI=%d dBm\n",
      WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else if(event==ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
    Serial.printf("[WiFi] Desconexion. reason=%u (codigo del controlador, no wl_status)\n",
      (unsigned)info.wifi_sta_disconnected.reason);
  }
}
void persist() {
  if(prefs.putBytes("queue", &queueData, sizeof(queueData))!=sizeof(queueData))
    Serial.println("ERROR al persistir cola: revisar memoria NVS");
}
void removeHead() {
  if(!queueData.count) return;
  memmove(queueData.items,queueData.items+1,(--queueData.count)*sizeof(Sample));
  persist(); backoff=1000; nextSend=millis()+100;
}
void setup() {
  Serial.begin(115200);
  delay(200);
  esp_reset_reason_t reset=esp_reset_reason();
  Serial.printf("\n[BOOT] Reinicio=%d: %s\n",(int)reset,resetName(reset));
  Serial.printf("[BOOT] Chip=%s, flash=%lu bytes, PSRAM habilitada=%lu bytes\n",
    ESP.getChipModel(),(unsigned long)ESP.getFlashChipSize(),(unsigned long)ESP.getPsramSize());
  Serial.printf("[BOOT] Sensor=DHT%d, GPIO=%d\n",DHT_TYPE,DHT_PIN);
  dht.begin();
  if(!prefs.begin("health-monitor",false)) Serial.println("[NVS] No se pudo abrir almacenamiento de la cola");
  if(prefs.getBytesLength("queue")==sizeof(queueData)) prefs.getBytes("queue", &queueData, sizeof(queueData));
  if(queueData.version!=1 || queueData.count>60) { memset(&queueData,0,sizeof(queueData)); queueData.version=1; }
  snprintf(bootId,sizeof(bootId),"%08lx%08lx%08lx%08lx",(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random());
  WiFi.persistent(false); // Las credenciales se leen de config.h; no reescribir flash.
  WiFi.onEvent(onWiFiEvent);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  nextWifi = millis() + 30000; // Dar tiempo al primer intento y a DHCP.
  Serial.println("[WiFi] Conexion iniciada en banda 2.4 GHz; no se imprimen credenciales");
  configTime(0,0,"pool.ntp.org","time.google.com");
#ifdef API_CA_CERT
  apiNetwork.setCACert(API_CA_CERT); // Validacion CA y nombre; nunca setInsecure().
  apiNetwork.setHandshakeTimeout(3);
  Serial.println("[BOOT] Transporte=HTTPS; cada muestra se retira al recibir respuesta 2xx");
#else
  Serial.println("[BOOT] Transporte=HTTP sin cifrar; solo para LAN");
#endif
  nextRead=millis()+2000;
}
void loop() {
  uint32_t now=millis();
  if(WiFi.status()!=WL_CONNECTED && due(now,nextWifi)) {
    Serial.printf("[WiFi] Sin IP. Estado=%d, uptime=%lu s, heap libre=%lu bytes\n",
      (int)WiFi.status(),(unsigned long)(now/1000),(unsigned long)ESP.getFreeHeap());
    // Respaldo de AutoReconnect, con intervalo amplio para no interrumpir
    // continuamente asociacion/DHCP. No reiniciar la placa por un fallo Wi-Fi.
    WiFi.reconnect();
    nextWifi = now + 30000;
  }
  if(due(now,nextRead)) {
    nextRead=now+10000;
    float h=NAN, t=NAN;
    bool valid=dht.read(t,h);
    if(!valid||isnan(t)||isnan(h)||h<0||h>100 || t<(DHT_TYPE==DHT11?0:-40) || t>(DHT_TYPE==DHT11?50:80)) Serial.println("[DHT] Lectura invalida: revisar DATA en GPIO4, alimentacion y GND");
    else if(queueData.count==60) Serial.println("Cola llena: se descarta muestra nueva");
    else {
      Sample &s=queueData.items[queueData.count++];
      s.t=t; s.h=h; s.seq=sequenceNumber++; strcpy(s.boot,bootId);
      time_t epoch=time(nullptr); s.epoch=epoch>1700000000?(uint64_t)epoch:0;
      Serial.printf("[DHT] Temperatura=%.1f C, humedad=%.1f %%\n",t,h);
      persist();
    }
  }
  if(WiFi.status()==WL_CONNECTED && queueData.count && due(now,nextSend)) {
    Sample &s=queueData.items[0];
    JsonDocument doc;
    doc["device_code"]=DEVICE_CODE; doc["temperature_c"]=s.t; doc["humidity_percent"]=s.h;
    doc["boot_id"]=s.boot; doc["sequence_number"]=s.seq;
    if(s.epoch) { time_t epoch=s.epoch; struct tm utc; gmtime_r(&epoch,&utc); char stamp[24]; strftime(stamp,sizeof(stamp),"%Y-%m-%dT%H:%M:%SZ",&utc); doc["measured_at"]=stamp; }
    else doc["measured_at"]=nullptr; // Sin NTP: servidor usa recepción; no inventar fecha histórica.
    String body; serializeJson(doc,body);
#ifdef API_CA_CERT
    HTTPClient http; http.setConnectTimeout(3000); http.setTimeout(5000); // Internet y TLS: mas margen que en LAN.
    http.begin(apiNetwork,API_URL);
#else
    HTTPClient http; http.setConnectTimeout(1500); http.setTimeout(2000);
    http.begin(API_URL);
#endif
    http.addHeader("Content-Type","application/json"); http.addHeader("X-API-Key",API_KEY);
    int code=http.POST(body); Serial.printf("POST %d, pendientes %lu\n",code,(unsigned long)queueData.count);
    http.end();
    if(code>=200 && code<300) {
      removeHead();
    } else {
      // También conserva 4xx para que el operador corrija credenciales/configuración.
      backoff=backoff<30000?backoff*2:60000;
    }
    nextSend=millis()+backoff;
  }
  delay(5); // Cede CPU; las operaciones de red tienen tiempo de espera acotado.
}
