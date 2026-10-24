# Captura de la unidad física UM1

La captura usa el mismo POST /api/v1/readings que el simulador, con el código de dispositivo registrado y su API Key. El firmware transmite automáticamente una muestra válida cada 10 segundos. El dashboard consulta las mediciones guardadas cada 5 segundos. No es necesario activar un modo de simulación ni ejecutar simulate.py para recibir el ESP32.

Abrir [dashboard de UM1](http://localhost:8000/?device_code=UM1). La URL permite seleccionar cualquier código registrado. Sin un código explícito, se selecciona la unidad de la medición más reciente. El estado de recepción se calcula desde received_at sin aplicar el filtro histórico: después de 30 s sin muestras avisa que la recepción no es reciente. El último valor guardado permanece visible con su fecha.

## Configuración local ya preparada

- Device code del firmware: UM1, registrado y activo como DHT11.
- Destino: `http://IP_LAN_DEL_SERVIDOR:8000/api/v1/readings`; usar la IP actual del servidor. Al migrar a Ubuntu, usar la IP de la VM según [la guía de instalación](ubuntu-virtualbox.md). Una IP anterior puede dejar de funcionar si cambia la asignación DHCP.
- API Key: debe coincidir con .env; no se publica.
- Mantener Docker Desktop y los servicios del Compose en funcionamiento.
- Alimentar el ESP32 y mantenerlo en una red que alcance la IP LAN del servidor. No necesita USB para transmitir si tiene otra fuente de alimentación adecuada.

## Comprobar recepción real

Con el dispositivo encendido, desde PowerShell en la raíz:

```powershell
.venv/Scripts/python scripts/verify_device.py --device UM1 --samples 3 --timeout 45
docker compose exec api python scripts/verify_csv.py
```

verify_device.py solo consulta la API: no genera ni inserta datos. Registra una ID inicial y espera nuevas IDs; un histórico antiguo por sí solo no supera esta comprobación. La identidad de dispositivo es lógica y la API Key es compartida en este prototipo; no es una atestación criptográfica del hardware.

En el monitor serie a 115200 deben aparecer una lectura DHT válida y `POST 200`. Lectura inválida: revisar sensor/cableado; POST negativo: conectividad con el servidor; 401: API Key; 404: Device code; 422: validar formato/rangos.

## Evidencia encontrada el 20 de octubre

Al revisar el sistema se encontraron 374 filas totales, con coincidencia exacta PostgreSQL/CSV. La última muestra de UM1 tenía ID 374: 27.1 °C, 71 %RH, medida a las 10:28:24 y recibida a las 10:28:25 (America/Bogota). Su secuencia 358 y el histórico muestran muestras del código UM1 a intervalos de unos 10 segundos. Los registros del código esp32-01 se conservan y pueden consultarse por separado; no se borró ningún dato.

En el momento inicial de esta revisión esa última muestra ya tenía varios minutos y no había puerto USB del ESP32 disponible. Se mostró como histórico sin recepción reciente.

La recepción se reanudó durante la comprobación. verify_device.py verificó tres muestras nuevas consecutivas, IDs 383, 384 y 385, recibidas a las 10:33:48, 10:33:58 y 10:34:08 (America/Bogota), con 27.1 °C y 72 %RH. Además se leyeron directamente por COM4 dos pares de mensajes DHT válido / POST 200. El dashboard de UM1 mostró recepción activa y valores coincidentes.

La comparación final confirmó coincidencia exacta de 389 filas entre PostgreSQL y CSV. No se ejecutó el simulador ni se inyectaron muestras durante esta verificación. Las muestras anteriores se conservan. Esta prueba confirma el circuito sensor → ESP32 → Wi-Fi → API → PostgreSQL/CSV → dashboard en la sesión observada.
