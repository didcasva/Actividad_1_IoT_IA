#include <WiFi.h>
#include <HTTPClient.h>
#include "BoundedDHT.h"
#include <ArduinoJson.h>
#include <Preferences.h>
#include <esp_system.h>
#include <time.h>
#include "config.h"
#if __has_include("mqtt.config.h")
#include "mqtt.config.h"
#endif
#ifdef MQTT_HOST
#include <MQTT.h>
#if MQTT_TLS
#include <WiFiClientSecure.h>
WiFiClientSecure mqttNetwork;
#else
WiFiClient mqttNetwork;
#endif
MQTTClient mqtt(1024);
String telemetryTopic, ackTopic, statusTopic;
bool pendingAck=false;
char ackBoot[33];
uint32_t ackSequence=0, nextMqtt=0, mqttBackoff=1000;
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
#ifdef MQTT_HOST
void onMqttMessage(String &topic, String &payload) {
  // La biblioteca puede invocar este callback durante publish QoS 1.
  // Solo registrar el ACK: no publicar, suscribir ni modificar la cola aqui.
  if(topic!=ackTopic || payload.length()>512) return;
  JsonDocument doc;
  if(deserializeJson(doc,payload)) return;
  if(strcmp(doc["status"]|"","stored")!=0 ||
     strcmp(doc["device_code"]|"",DEVICE_CODE)!=0 ||
     !doc["sequence_number"].is<uint32_t>()) return;
  const char* boot=doc["boot_id"]|"";
  if(strlen(boot)!=32) return;
  strcpy(ackBoot,boot); ackSequence=doc["sequence_number"].as<uint32_t>(); pendingAck=true;
}
void consumeMqttAck() {
  if(!pendingAck) return;
  pendingAck=false;
  if(queueData.count && queueData.items[0].seq==ackSequence &&
     strcmp(queueData.items[0].boot,ackBoot)==0) {
    removeHead();
    Serial.printf("[MQTT] Guardado confirmado en PostgreSQL/CSV; pendientes=%lu\n",(unsigned long)queueData.count);
  }
}
void maintainMqtt(uint32_t now) {
  if(WiFi.status()!=WL_CONNECTED) return;
  mqtt.loop();
  consumeMqttAck();
  if(mqtt.connected() || !due(now,nextMqtt)) return;
  String id="rutasalud-"+WiFi.macAddress(); id.replace(":","");
  if(mqtt.connect(id.c_str(),MQTT_USERNAME,MQTT_PASSWORD)) {
    if(mqtt.subscribe(ackTopic,1) && mqtt.publish(statusTopic,"online",true,1)) {
      Serial.println("[MQTT] Conectado y suscrito al topic de confirmacion");
      mqttBackoff=1000; nextSend=millis();
    } else {
      mqtt.disconnect();
      Serial.println("[MQTT] Fallo al preparar suscripcion/estado");
    }
  } else {
    Serial.printf("[MQTT] Conexion pendiente: error=%d, retorno=%d\n",mqtt.lastError(),mqtt.returnCode());
  }
  nextMqtt=millis()+mqttBackoff;
  if(!mqtt.connected()) mqttBackoff=mqttBackoff<30000?mqttBackoff*2:60000;
}
#endif
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
#ifdef MQTT_HOST
  telemetryTopic=String("rutasalud/")+DEVICE_CODE+"/telemetria";
  ackTopic=String("rutasalud/")+DEVICE_CODE+"/ack";
  statusTopic=String("rutasalud/")+DEVICE_CODE+"/estado";
#if MQTT_TLS
  mqttNetwork.setCACert(MQTT_CA_CERT); // Validacion CA y nombre; nunca setInsecure().
  mqttNetwork.setHandshakeTimeout(3);
#endif
  mqttNetwork.setTimeout(2000);
  mqtt.begin(MQTT_HOST,MQTT_PORT,mqttNetwork);
  mqtt.setOptions(30,true,1500);
  mqtt.onMessage(onMqttMessage);
  mqtt.setWill(statusTopic.c_str(),"offline",true,1);
  Serial.println("[BOOT] Transporte=MQTT; se espera acuse de guardado antes de retirar cada muestra");
#else
  Serial.println("[BOOT] Transporte=HTTP; generar mqtt.config.h para activar MQTT");
#endif
  nextRead=millis()+2000;
}
void loop() {
  uint32_t now=millis();
#ifdef MQTT_HOST
  maintainMqtt(now);
#endif
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
#ifdef MQTT_HOST
    if(!mqtt.connected()) { delay(5); return; }
    const bool published=mqtt.publish(telemetryTopic,body,false,1);
    Serial.printf("[MQTT] Publicacion=%s; pendientes=%lu; esperando acuse de la aplicacion\n",
      published?"aceptada por broker":"pendiente",(unsigned long)queueData.count);
    // PUBACK solo confirma broker. La muestra permanece en NVS hasta el ACK
    // de aplicacion con la misma unidad, boot_id y sequence_number.
    backoff=backoff<30000?backoff*2:60000;
#else
    HTTPClient http; http.setConnectTimeout(1500); http.setTimeout(2000);
    http.begin(API_URL); http.addHeader("Content-Type","application/json"); http.addHeader("X-API-Key",API_KEY);
    int code=http.POST(body); Serial.printf("POST %d, pendientes %lu\n",code,(unsigned long)queueData.count);
    http.end();
    if(code>=200 && code<300) {
      removeHead();
    } else {
      // También conserva 4xx para que el operador corrija credenciales/configuración.
      backoff=backoff<30000?backoff*2:60000;
    }
#endif
    nextSend=millis()+backoff;
  }
  delay(5); // Cede CPU; las operaciones de red tienen tiempo de espera acotado.
}
