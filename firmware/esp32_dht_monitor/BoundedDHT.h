#pragma once
#include <Arduino.h>
#include <driver/gpio.h>
#include <esp_timer.h>

static constexpr uint8_t DHT11 = 11;
static constexpr uint8_t DHT22 = 22;

// Lector ESP32 con limites de tiempo reales. No cuenta iteraciones de
// digitalRead: su coste varia entre versiones del core. Una linea fija o
// desconectada siempre termina y devuelve false, sin desactivar el watchdog.
class BoundedDHT {
 public:
  BoundedDHT(uint8_t pin, uint8_t type) : pin_(pin), type_(type) {}
  void begin() { pinMode(pin_, INPUT_PULLUP); }

  bool read(float &temperature, float &humidity) {
    uint8_t bytes[5] = {};
    pinMode(pin_, OUTPUT_OPEN_DRAIN);
    digitalWrite(pin_, LOW);
    // La senal de inicio larga se realiza CON interrupciones habilitadas.
    delay(type_ == DHT11 ? 20 : 2);

    bool ok = true;
    portENTER_CRITICAL(&mux_);
    deadline_ = esp_timer_get_time() + 8000; // Maximo global: 8 ms.
    pinMode(pin_, INPUT_PULLUP); // Liberar bus, respuesta del sensor en 20-40 us.
    ok = waitForLow();
    if(ok) ok = pulse(LOW) >= 0;
    if(ok) ok = pulse(HIGH) >= 0;
    for(unsigned bit = 0; ok && bit < 40; ++bit) {
      int low = pulse(LOW);
      int high = low >= 0 ? pulse(HIGH) : -1;
      if(low < 0 || high < 0) {
        ok = false; // Abortar EN EL PRIMER timeout, sin recorrer otros pulsos.
      } else {
        bytes[bit / 8] = (bytes[bit / 8] << 1) | (high > 50 ? 1 : 0);
      }
    }
    portEXIT_CRITICAL(&mux_);
    if(!ok || uint8_t(bytes[0]+bytes[1]+bytes[2]+bytes[3]) != bytes[4]) return false;

    if(type_ == DHT11) {
      humidity = bytes[0] + bytes[1] * 0.1f;
      temperature = bytes[2] + (bytes[3] & 0x7f) * 0.1f;
      if(bytes[3] & 0x80) temperature = -temperature;
    } else {
      humidity = ((uint16_t(bytes[0]) << 8) | bytes[1]) * 0.1f;
      temperature = (((uint16_t(bytes[2] & 0x7f) << 8) | bytes[3])) * 0.1f;
      if(bytes[2] & 0x80) temperature = -temperature;
    }
    return true;
  }

 private:
  uint8_t pin_, type_;
  int64_t deadline_ = 0;
  portMUX_TYPE mux_ = portMUX_INITIALIZER_UNLOCKED;

  bool waitForLow() {
    int64_t start = esp_timer_get_time();
    while(gpio_get_level(gpio_num_t(pin_)) != LOW) {
      int64_t now = esp_timer_get_time();
      if(now - start >= 200 || now >= deadline_) return false;
    }
    return true;
  }

  int pulse(int level) {
    int64_t start = esp_timer_get_time();
    while(gpio_get_level(gpio_num_t(pin_)) == level) {
      int64_t now = esp_timer_get_time();
      if(now - start >= 120 || now >= deadline_) return -1;
    }
    return int(esp_timer_get_time() - start);
  }
};
