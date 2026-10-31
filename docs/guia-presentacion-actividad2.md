# Ruta Salud: guía para la presentación de la actividad 2

**Corte de la evidencia:** 30 de octubre de 2026, hora de Colombia (`America/Bogota`). Algunos registros del servidor llevan fecha 31 de octubre porque están en UTC.

Este guion explica el sistema que quedó desplegado y las pruebas confirmadas. La [bitácora técnica](bitacora-aws-actividad2.md) contiene los comandos y el registro de cambios. La consigna original de la actividad 2 no está incorporada al repositorio; este documento describe la implementación, sin certificar el cumplimiento de una rúbrica que no se ha contrastado.

## Mensaje de apertura

> Ruta Salud captura temperatura y humedad ambiental de una unidad móvil mediante un ESP32 y un DHT11. El dispositivo transmite las muestras por MQTT con TLS hacia AWS. Allí conservamos los registros en PostgreSQL, generamos un CSV y mantenemos una proyección de series de tiempo en InfluxDB. Grafana permite consultar las mediciones y evaluar alertas. Comprobamos el flujo con el sensor físico, la coincidencia de los registros y la activación y resolución de una alerta de falta de datos.

## Arquitectura que se debe mostrar

```mermaid
flowchart LR
    SENSOR["DHT11 + ESP32-S3<br/>Unidad UM1"]
    OPERADOR["Operador en navegador"]
    subgraph PUBLICA["EC2 pública · 192.168.0.200 · IP elástica 3.231.16.96"]
        MQTT["Mosquitto"]
        RECEPTOR["Receptor Python"]
        CSV["CSV persistente"]
        CADDY["Caddy · HTTPS"]
        API["FastAPI + dashboard original"]
        GRAFANA["Grafana 13.2.5"]
    end
    subgraph PRIVADA["EC2 privada · 192.168.1.142"]
        PG[("PostgreSQL 16.15")]
        INFLUX[("InfluxDB 2.7.12")]
    end
    DISCORD["Discord · complemento opcional"]
    SENSOR -->|"MQTT TLS · 8883"| MQTT
    MQTT --> RECEPTOR
    RECEPTOR --> PG
    RECEPTOR --> CSV
    RECEPTOR --> INFLUX
    RECEPTOR -->|"ACK stored"| MQTT
    MQTT -->|"ACK"| SENSOR
    OPERADOR -->|"HTTPS · 443"| CADDY
    CADDY --> API
    CADDY --> GRAFANA
    API -->|"Consultas SQL"| PG
    GRAFANA -->|"Consulta Flux · 8086 privado"| INFLUX
    GRAFANA -.-> DISCORD
```

PostgreSQL e InfluxDB reciben las conexiones por la red privada. La comunicación exterior del ESP32 utiliza TLS y la del navegador HTTPS. En esta instalación las conexiones internas a PostgreSQL y a InfluxDB no tienen TLS adicional.

## Guion de exposición de 8 a 10 minutos

### 1. Problemática y objetivo

Las mediciones ocasionales y los registros manuales dificultan reconstruir las condiciones ambientales de una jornada. El objetivo del prototipo es automatizar la captura, conservar el histórico por unidad y facilitar su consulta. Se mide el ambiente del punto donde se instala el sensor; no se capturan datos de pacientes ni temperatura corporal.

**Frase de apoyo:** “Buscamos que cada lectura tenga unidad, fecha y trazabilidad, y que una interrupción de recepción también sea visible”.

### 2. Hardware y datos transmitidos

La unidad física usa un ESP32-S3 y un sensor DHT11. El firmware toma una muestra cada diez segundos y construye un JSON con seis campos:

| Campo | Explicación para la exposición |
| --- | --- |
| `device_code` | Unidad que envía, por ejemplo `UM1`. |
| `temperature_c` | Temperatura ambiental en grados Celsius. |
| `humidity_percent` | Humedad relativa en porcentaje. |
| `boot_id` | Identificador del arranque del dispositivo. |
| `sequence_number` | Número de muestra dentro de ese arranque. |
| `measured_at` | Fecha de la medición en UTC, o `null` si aún no hay hora sincronizada. |

El servidor agrega `id`, `device_id` y `received_at`. Si falta la hora del sensor, asigna la recepción a `measured_at`; eso no reconstruye una hora histórica desconocida.

### 3. Cómo se envía la información

En el despliegue actual se utiliza **MQTT con TLS en el puerto 8883**. El topic de datos es `rutasalud/UM1/telemetria`.

La instrucción de publicación en el [firmware](../firmware/esp32_dht_monitor/esp32_dht_monitor.ino) es:

```cpp
const bool published = mqtt.publish(telemetryTopic, body, false, 1);
```

`body` contiene el JSON; `false` indica que la publicación no es retenida y `1` selecciona QoS 1. También existe `http.POST(body)` como alternativa de compilación. El dashboard utiliza consultas HTTP `GET` a la API.

El ESP32 conserva la muestra en NVS hasta recibir el ACK de la aplicación. En AWS, con InfluxDB habilitado, ese ACK se publica después de completar PostgreSQL, CSV e InfluxDB. El acuse del broker por sí solo no confirma esos tres destinos.

### 4. Por qué usamos PostgreSQL, CSV e InfluxDB

| Componente | Función |
| --- | --- |
| PostgreSQL | Fuente de verdad, inventario de dispositivos e histórico con restricciones de integridad. |
| CSV | Archivo físico recuperable y formato de exportación para consultar o analizar las mediciones. |
| InfluxDB | Proyección de series de tiempo que consulta Grafana. |

La identidad única `(device_id, boot_id, sequence_number)` evita insertar de nuevo una muestra reintentada. El CSV se reconstruye desde PostgreSQL y se reemplaza mediante un archivo temporal. InfluxDB puede recargarse desde el mismo histórico con `reconcile_influx.py`.

**Límite que se debe explicar:** las tres escrituras no forman una transacción distribuida. PostgreSQL confirma primero; un fallo posterior requiere reintento o reconciliación.

### 5. Qué aporta Grafana

Grafana consulta el bucket `telemetria`, de la organización `rutasalud`, usando un token de solo lectura. El dashboard **Monitoreo ambiental** muestra temperatura, humedad, sus gráficas y las alertas. Se publica por el mismo HTTPS de la aplicación en la ruta `/grafana/`.

Hay tres reglas aprovisionadas desde archivos del repositorio:

| Regla | Condición del prototipo |
| --- | --- |
| Temperatura fuera de rango | Última lectura menor que 15 °C o mayor que 30 °C. |
| Humedad fuera de rango | Última lectura menor que 30 % o mayor que 75 %. |
| Sin mediciones de UM1 | Ausencia de puntos de UM1 en la ventana de los últimos dos minutos. |

Las reglas tienen una espera de un minuto y evaluación cada minuto; el disparo no es instantáneo. Los umbrales son de demostración académica, no criterios clínicos ni límites regulatorios validados.

Discord se añadió como **canal opcional de notificación**. La evaluación y visualización de las alertas pertenecen a Grafana. No se presenta Discord como un requisito acreditado de la consigna.

### 6. Resultados que sí podemos presentar

| Evidencia | Resultado confirmado |
| --- | --- |
| Primera carga del histórico en AWS | 2.951 mediciones coincidentes entre PostgreSQL, InfluxDB y CSV en ese corte. |
| Recepción después de encender el ESP32 | Tres muestras nuevas: IDs 3184, 3185 y 3186, con 27,6 °C y 68 % de humedad. |
| Comparación después de la recuperación | 3.186 mediciones coincidentes entre PostgreSQL e InfluxDB, sin puntos adicionales. |
| Grafana por HTTPS | Endpoint de salud con `database: ok` y versión 13.2.5. |
| Dashboard y reglas | Visualización de datos y tres reglas confirmadas por el usuario. |
| Desconexión del sensor | Alerta “Sin mediciones de UM1” en `Firing` y aviso real recibido en Discord. |
| Reconexión del sensor | Nuevas lecturas, retorno a `Normal`, mensaje `Resolved` y gráficas actualizadas confirmados por el usuario. |

Los conteos pertenecen a momentos distintos: el sistema siguió recibiendo muestras. La comparación final de 3.186 corresponde a SQL/InfluxDB; la evidencia CSV compartida corresponde al corte inicial de 2.951.

Captura aportada durante la verificación guiada: las tres reglas están aprovisionadas y muestran estado `Normal` en ese momento.

![Tres reglas de Grafana aprovisionadas en estado Normal](evidencias/actividad2-aws-reglas-normal.png)

### 7. Cómo conservamos los datos y arrancan los servicios

Los datos se guardan en volúmenes de Docker y la configuración en archivos del disco EBS. Docker y containerd quedaron habilitados al inicio en ambas EC2. Los siete servicios permanentes tienen `restart: unless-stopped`; la swap de 1 GiB en cada servidor está registrada en `/etc/fstab`. El temporizador del certificado está habilitado y activo en la pública.

**Estado de la prueba:** se comprobó la configuración de arranque. No se recibió evidencia del reinicio completo de ambas EC2; esa comprobación queda pendiente. Persistencia en un volumen y respaldo fuera de la instancia son necesidades diferentes.

### 8. Cierre y alcance

> El resultado es un flujo de monitoreo ambiental desplegado en dos EC2, probado con el sensor físico y con verificación de consistencia del histórico. También comprobamos que la falta de recepción se detecta y que la alerta se resuelve al recuperar las mediciones. El siguiente trabajo es validar el arranque tras reinicio, ampliar las pruebas de estabilidad y formalizar los respaldos y la operación prolongada.

## Demostración recomendada

1. Abrir el [dashboard original de UM1](https://3.231.16.96/?device_code=UM1) y el [dashboard de Grafana](https://3.231.16.96/grafana/d/rutasalud-ambiente/monitoreo-ambiental?var-unidad=UM1&from=now-15m&to=now). Ingresar las credenciales de forma privada.
2. Con el ESP32 encendido, mostrar una lectura y su actualización aproximadamente cada diez segundos.
3. Mostrar las tres reglas en Grafana y explicar `Normal`, `Pending` y `Firing`.
4. Para una demostración en vivo de falta de datos, apagar el ESP32 y aprovechar la espera de varios minutos para explicar la persistencia y los resultados. La captura histórica del disparo es evidencia de una prueba anterior, no una ejecución nueva.
5. Encenderlo, mostrar mediciones recientes y comprobar el retorno a `Normal`. Si se usa el complemento de Discord, mostrar disparo y resolución sin exponer el webhook.

No cargar datos sintéticos en la unidad física de AWS para forzar umbrales. Las pruebas sintéticas anteriores se hicieron en entornos aislados. El disparo físico de las reglas de temperatura y humedad no se verificó en este despliegue.

## Preguntas frecuentes para la sustentación

| Pregunta | Respuesta breve |
| --- | --- |
| ¿Usamos HTTP o MQTT desde el ESP32? | MQTT con TLS en AWS. HTTP POST queda como alternativa; el navegador consulta por HTTP sobre HTTPS. |
| ¿Por qué dos servidores? | Para separar los servicios públicos de la persistencia accesible por la VPC. |
| ¿Qué evita los duplicados? | La identidad única del dispositivo, arranque y secuencia, además de conservarla en cada reintento. |
| ¿Qué pasa si no hay conexión? | El ESP32 conserva hasta 60 muestras en NVS y reintenta. La cola es limitada y rechaza muestras nuevas cuando se llena. |
| ¿Qué significa el ACK? | Que la aplicación completó los destinos habilitados; no es solo la aceptación del broker. |
| ¿El CSV descargado es el archivo físico completo? | La exportación del dashboard se genera desde PostgreSQL y aplica los filtros; el archivo persistente conserva todo el histórico. |
| ¿Por qué Discord? | Es una elección opcional para avisos externos. La consigna de la actividad 2 no se ha contrastado en este repositorio. |
| ¿Los servicios arrancan solos? | La política y los servicios de Ubuntu están configurados. Falta registrar la prueba de reinicio completo. |
| ¿El prototipo demuestra cumplimiento sanitario? | No. Se requiere definir el uso, instrumentos adecuados, calibración, cobertura y procesos de calidad. |

## Material de consulta

- [Bitácora técnica y operación de AWS](bitacora-aws-actividad2.md).
- [Registro cronológico de validación](validation.md#actividad-2-en-aws).
- [Datos del ESP32, métodos HTTP/MQTT y CSV](comunicacion-y-csv.md).
- [Problemática y modelo relacional](modelo-datos-y-problematica.md).
- [Grafana y configuración de alertas](grafana.md).
