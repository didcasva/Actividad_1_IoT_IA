# Ruta Salud: problemática, arquitectura en AWS y modelo de datos

Documento de apoyo para la exposición académica. Esquema contrastado con los modelos y la migración inicial del proyecto el 30 de octubre de 2026. Describe PostgreSQL; InfluxDB y Grafana se documentan en [datos](database.md#influxdb) y [Grafana](grafana.md).

## Problemática

Las unidades móviles de salud operan durante desplazamientos y jornadas de atención, con cambios de clima, ventilación, apertura de puertas y disponibilidad de energía y conectividad. Estas condiciones pueden modificar la temperatura y la humedad del área monitoreada. Cuando el seguimiento depende de anotaciones manuales o mediciones ocasionales, pueden quedar intervalos sin información, errores de transcripción y dificultades para reconstruir las condiciones de una jornada.

La falta de registros centralizados dificulta detectar desviaciones y preparar soportes verificables para los informes de calidad, las auditorías y los requerimientos sanitarios que correspondan a los servicios prestados. Cuando existen medicamentos o insumos con condiciones específicas de almacenamiento, la medición debe representar esa zona y contrastarse con los requisitos de los productos; una lectura en el área de atención no demuestra las condiciones de un refrigerador o de otro compartimiento.

## Objetivo

Automatizar la captura y conservación de temperatura y humedad por unidad móvil, para consultar el histórico por fechas y disponer de evidencia que apoye la gestión ambiental y la elaboración de informes.

```mermaid
flowchart LR
    A[Unidad móvil: zona monitoreada] --> B[DHT11 y ESP32]
    B -->|MQTT con TLS| C[Mosquitto en AWS]
    C --> D[Receptor Python]
    D --> E[(PostgreSQL)]
    D --> F[Archivo CSV]
    E --> G[Dashboard y consulta histórica]
    F --> H[Soporte para elaboración de informes]
```

La consulta histórica y la exportación CSV existen. Grafana genera alertas de umbral de demostración. La generación de informes aprobados y el registro de acciones correctivas todavía no están implementados.

## Arquitectura de los servidores en AWS

El despliegue utiliza **dos servidores EC2 Ubuntu con Docker**, dentro de una misma red virtual de AWS (VPC). El servidor público recibe las mediciones y atiende el dashboard; el servidor privado conserva la base de datos. La aplicación se comunica con PostgreSQL mediante las direcciones privadas de la VPC.

```mermaid
flowchart TB
    ESP["Unidad móvil UM1<br/>DHT11 + ESP32-S3"]
    WEB["Operador<br/>Navegador web"]

    subgraph AWS["AWS · VPC del proyecto"]
        subgraph PUBLICA["Subred pública"]
            subgraph APP["EC2 pública · Ubuntu + Docker<br/>IP elástica: 3.231.16.96<br/>IP privada: 192.168.0.200"]
                BROKER["Mosquitto<br/>Broker MQTT"]
                WORKER["Receptor MQTT<br/>Validación y guardado"]
                CADDY["Caddy<br/>HTTPS y autenticación"]
                API["FastAPI<br/>Dashboard y consultas"]
                CSV["Volumen persistente<br/>Archivo CSV"]
            end
        end

        subgraph PRIVADA["Subred privada"]
            subgraph DATOS["EC2 privada · Ubuntu + Docker<br/>IP privada: 192.168.1.142<br/>Sin IP pública"]
                PG[("PostgreSQL 16<br/>Base de datos monitor")]
                VOL["Volumen persistente<br/>Datos de PostgreSQL"]
                PG --- VOL
            end
        end
    end

    ESP -->|"Internet · MQTT con TLS · 8883"| BROKER
    WEB -->|"Internet · HTTPS · 443"| CADDY
    BROKER -->|"MQTT interno de Docker · 1883"| WORKER
    CADDY -->|"HTTP interno · 8000"| API
    WORKER -->|"Escritura · red privada · 5432"| PG
    API -->|"Consultas e ingestión HTTP · red privada · 5432"| PG
    WORKER --> CSV
    API --> CSV
```

### Función de cada servidor

| Servidor | Ubicación y direcciones | Responsabilidad |
| --- | --- | --- |
| **Público: aplicación y broker** | Subred pública. IP elástica `3.231.16.96`; IP privada `192.168.0.200`. | Mosquitto recibe las publicaciones del ESP32; el receptor valida y almacena las muestras; FastAPI sirve el dashboard y las consultas; Caddy proporciona HTTPS y autenticación. También se conserva el CSV. |
| **Privado: base de datos** | Subred privada. IP `192.168.1.142`, sin IP pública. | PostgreSQL conserva las tablas `devices` y `sensor_readings` en un volumen persistente. Recibe las conexiones de la aplicación por la VPC. |

### Recorrido de una medición

1. El ESP32 publica temperatura y humedad en `rutasalud/UM1/telemetria`, utilizando MQTT con TLS y credenciales.
2. Mosquitto, en el servidor público, entrega la publicación al receptor suscrito.
3. El receptor valida el mensaje, guarda la muestra en PostgreSQL del servidor privado y completa el CSV en el servidor público.
4. Después del guardado, el receptor devuelve la confirmación por MQTT al ESP32.
5. El operador entra al dashboard por HTTPS; FastAPI consulta PostgreSQL y devuelve el histórico de la unidad.

### Acceso y separación de la red

| Conexión | Puerto TCP | Uso |
| --- | --- | --- |
| ESP32 → servidor público | `8883` | Telemetría MQTT protegida por TLS, usuario y permisos por topic. |
| Navegador → servidor público | `443` | Consulta del dashboard mediante HTTPS y autenticación. |
| Autoridad certificadora → servidor público | `80` | Validación para emitir y renovar el certificado; el resto de solicitudes HTTP se redirige a HTTPS. |
| Servidor público → servidor privado | `5432` | Acceso a PostgreSQL por la VPC. La regla de entrada de la base se limita al servidor público. |
| Administrador → servidor público → servidor privado | `22` | Administración SSH con PuTTY y salto desde el servidor público al privado. |

El ESP32 y el navegador se conectan a los servicios del servidor público. El puerto PostgreSQL se publica sobre la IP privada y su acceso se restringe mediante el grupo de seguridad. Los puertos `1883` y `8000` se utilizan dentro del despliegue, sin publicación directa en Internet. Los certificados TLS del servidor público se gestionan con Certbot y una tarea de renovación automática.

## Modelo relacional actual

```mermaid
erDiagram
    devices ||--o{ sensor_readings : registra
    devices {
        integer id PK "Identificador del dispositivo"
        varchar80 device_code UK "Código único, por ejemplo UM1"
        varchar120 name "Nombre de la unidad o dispositivo"
        varchar10 sensor_type "DHT11 o DHT22"
        varchar200 location "Zona monitoreada; no GPS"
        timestamptz created_at "Fecha de registro"
        boolean is_active "Habilitado para recibir datos"
    }
    sensor_readings {
        integer id PK "Identificador de la medición"
        integer device_id FK "Referencia a devices.id"
        float temperature_c "Temperatura en grados Celsius"
        float humidity_percent "Humedad relativa en porcentaje"
        timestamptz measured_at "Fecha atribuida a la medición"
        timestamptz received_at "Fecha de recepción en el servidor"
        varchar80 boot_id "Identificador del arranque del ESP32"
        integer sequence_number "Secuencia dentro del arranque"
    }
```

**Relación:** un dispositivo puede tener cero o muchas mediciones. Cada medición pertenece a un solo dispositivo. `device_code` es único. En el prototipo, `UM1` identifica el dispositivo asignado a una unidad móvil; no existe una tabla independiente de vehículos, sedes o zonas.

**PK:** clave primaria. **FK:** clave foránea. **UK:** valor único.

### Tabla `devices`: inventario del punto de medición

| Campo | Tipo | Función |
| --- | --- | --- |
| `id` | INTEGER, PK | Identificador interno. |
| `device_code` | VARCHAR(80), UNIQUE | Código enviado por el ESP32 y usado en MQTT. |
| `name` | VARCHAR(120) | Nombre descriptivo de la unidad o dispositivo. |
| `sensor_type` | VARCHAR(10) | Tipo de sensor: DHT11 o DHT22. |
| `location` | VARCHAR(200) | Descripción de la ubicación del sensor. |
| `created_at` | TIMESTAMPTZ | Fecha de creación del registro. |
| `is_active` | BOOLEAN | Permite aceptar o rechazar nuevas mediciones del dispositivo. |

### Tabla `sensor_readings`: histórico ambiental

| Campo | Tipo | Función |
| --- | --- | --- |
| `id` | INTEGER, PK | Identificador interno de la muestra. |
| `device_id` | INTEGER, FK | Vincula la muestra con su dispositivo. |
| `temperature_c` | FLOAT | Valor de temperatura en °C. |
| `humidity_percent` | FLOAT | Valor de humedad relativa en %. |
| `measured_at` | TIMESTAMPTZ | Instante de medición si el ESP32 tiene hora sincronizada. |
| `received_at` | TIMESTAMPTZ | Instante en que el servidor recibió la muestra. |
| `boot_id` | VARCHAR(80) | Permite distinguir los reinicios del dispositivo. |
| `sequence_number` | INTEGER | Distingue las muestras de un mismo arranque. |

Todos los campos son obligatorios en las tablas. El contrato de entrada admite `measured_at = null`: en ese caso, el servicio lo sustituye por la hora de recepción. Ese valor no permite reconstruir la hora original de una muestra almacenada sin reloj. La base actual no conserva un indicador explícito de esa sustitución.

### Integridad y trazabilidad existentes

- La clave foránea evita mediciones sin dispositivo registrado.
- La combinación única `(device_id, boot_id, sequence_number)` evita insertar dos veces una misma muestra cuando MQTT reintenta su entrega.
- Un índice por `(device_id, measured_at)` facilita las consultas de una unidad por tiempo.
- PostgreSQL verifica humedad entre 0 y 100 %, temperatura entre -40 y 80 °C y secuencia no negativa. El servicio restringe adicionalmente las lecturas DHT11 a 0-50 °C. Son validaciones de datos y sensor, **no umbrales sanitarios**.
- Las fechas se manejan con zona horaria; para presentar un informe debe indicarse la zona utilizada.
- El receptor confirma el guardado al ESP32 después de persistir PostgreSQL y completar CSV. El archivo conserva las mediciones, pero no es por sí mismo un informe firmado ni inalterable.

## Cómo los registros apoyarían un informe

Propuesta de contenido; no representa un formato oficial definido ni una funcionalidad completa existente.

| Contenido | Situación actual |
| --- | --- |
| Código de unidad y zona monitoreada | Disponible en `devices`. |
| Periodo y zona horaria del informe | Hay filtros por fechas; falta un informe formal con esos metadatos. |
| Temperatura y humedad por instante | Disponibles en `sensor_readings`. |
| Tabla de mediciones exportable | Exportación CSV disponible. |
| Mínimos, máximos y promedios del periodo | Calculables a partir de las lecturas; pendiente incorporarlos al informe. |
| Umbrales aplicables y su fundamento | Pendiente definirlos por zona, uso y requisitos de los productos. |
| Desviaciones, duración y acciones tomadas | Pendientes reglas, tratamiento de intervalos sin datos y bitácora de gestión. |
| Periodos sin recepción y cobertura de datos | Hay aviso de recepción atrasada; falta consolidar los vacíos en el informe. |
| Identificación y calibración del sensor | Solo consta el tipo; faltan serie, verificaciones y soportes de calibración. |
| Elaboración, revisión y aprobación | Pendientes responsables, versión del informe y trazabilidad de aprobación. |

Los huecos de conectividad deben aparecer como falta de información, no como evidencia de condiciones normales. La cola del ESP32 es limitada a 60 muestras; cuando se llena, descarta nuevas lecturas. Un laboratorio AWS apagado durante varias horas puede producir vacíos que no se recuperan por completo.

## Relación con los requisitos sanitarios en Colombia

Como referencia para sustentar el caso de uso, el numeral 7 del estándar 11.1.4 de la Resolución 3100 de 2019 aborda las condiciones de almacenamiento de medicamentos e insumos: cuando aplica, exige instrumentos de temperatura y humedad, así como evidencia de registro, control y gestión conforme a las condiciones del fabricante. Ver [texto en el normograma de Supersalud](https://normograma.supersalud.gov.co/compilacion/docs/resolucion_minsaludps_3100_2019.htm).

La Resolución 1403 de 2007 incluye condiciones ambientales y registros para el almacenamiento de medicamentos dentro de su ámbito de aplicación. Ver [texto en el normograma del Invima](https://normograma.invima.gov.co/compilacion/docs/resolucion_minproteccion_1403_2007.htm).

El proyecto aporta un prototipo de captura y evidencia ambiental. Su uso en informes regulatorios requiere concretar, con el responsable de calidad de la institución, el servicio y zona cubiertos, requisitos aplicables, instrumentos adecuados y su calibración, continuidad del registro, gestión de desviaciones y revisión de los informes. El prototipo con DHT11 no constituye por sí solo una certificación de cumplimiento ni una validación de cadena de frío.
