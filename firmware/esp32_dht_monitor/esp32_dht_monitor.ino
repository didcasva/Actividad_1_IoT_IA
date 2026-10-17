#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <time.h>
#include "config.h"

DHT dht(DHT_PIN, DHT_TYPE);
Preferences prefs;
// Cola persistente: 60 muestras = 10 minutos. Al llenarse se descarta
// explícitamente la muestra nueva; las pendientes mantienen su identidad.
struct Sample { float t, h; uint64_t epoch; uint32_t seq; char boot[33]; };
struct Queue { uint32_t version; uint32_t count; Sample items[60]; } queueData;
char bootId[33];
uint32_t sequenceNumber=0, nextRead=0, nextSend=0, nextWifi=0, backoff=1000;
bool due(uint32_t now, uint32_t deadline) { return (int32_t)(now-deadline)>=0; }
void persist() {
  if(prefs.putBytes("queue", &queueData, sizeof(queueData))!=sizeof(queueData))
    Serial.println("ERROR al persistir cola: revisar memoria NVS");
}
void setup() {
  Serial.begin(115200); dht.begin();
  prefs.begin("health-monitor",false);
  if(prefs.getBytesLength("queue")==sizeof(queueData)) prefs.getBytes("queue", &queueData, sizeof(queueData));
  if(queueData.version!=1 || queueData.count>60) { memset(&queueData,0,sizeof(queueData)); queueData.version=1; }
  snprintf(bootId,sizeof(bootId),"%08lx%08lx%08lx%08lx",(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random(),(unsigned long)esp_random());
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
  configTime(0,0,"pool.ntp.org","time.google.com");
  nextRead=millis()+2000;
}
void loop() {
  uint32_t now=millis();
  if(WiFi.status()!=WL_CONNECTED && due(now,nextWifi)) {
    WiFi.reconnect(); nextWifi=now+10000; Serial.println("Reconectando Wi-Fi…");
  }
  if(due(now,nextRead)) {
    nextRead=now+10000;
    float h=dht.readHumidity(), t=dht.readTemperature();
    if(isnan(t)||isnan(h)||h<0||h>100 || t<(DHT_TYPE==DHT11?0:-40) || t>(DHT_TYPE==DHT11?50:80)) Serial.println("Lectura DHT inválida");
    else if(queueData.count==60) Serial.println("Cola llena: se descarta muestra nueva");
    else {
      Sample &s=queueData.items[queueData.count++];
      s.t=t; s.h=h; s.seq=sequenceNumber++; strcpy(s.boot,bootId);
      time_t epoch=time(nullptr); s.epoch=epoch>1700000000?(uint64_t)epoch:0;
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
    HTTPClient http; http.setConnectTimeout(1500); http.setTimeout(2000);
    http.begin(API_URL); http.addHeader("Content-Type","application/json"); http.addHeader("X-API-Key",API_KEY);
    int code=http.POST(body); Serial.printf("POST %d, pendientes %lu\n",code,(unsigned long)queueData.count);
    http.end();
    if(code>=200 && code<300) {
      memmove(queueData.items,queueData.items+1,(--queueData.count)*sizeof(Sample)); persist(); backoff=1000;
    } else {
      // También conserva 4xx para que el operador corrija credenciales/configuración.
      backoff=backoff<30000?backoff*2:60000;
    }
    nextSend=millis()+backoff;
  }
  delay(5); // Cede CPU; no espera activa de Wi-Fi ni NTP. HTTP tiene timeout acotado.
}
