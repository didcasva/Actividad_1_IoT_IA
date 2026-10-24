"""Register sensor metadata without creating measurements or replacing existing devices."""
import argparse
from sqlalchemy import select
from app.core.database import Session
from app.models.entities import Device


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", default="UM1")
    parser.add_argument("--sensor", choices=["DHT11", "DHT22"], default="DHT11")
    parser.add_argument("--name", default="Unidad móvil de salud 01")
    parser.add_argument("--location", default="Área de atención de la unidad móvil 01")
    args = parser.parse_args()
    if not 1 <= len(args.code) <= 80 or len(args.name) > 120 or len(args.location) > 200:
        parser.error("Metadatos fuera de los límites admitidos")
    with Session.begin() as db:
        device = db.scalar(select(Device).where(Device.device_code == args.code))
        if device:
            if device.sensor_type != args.sensor or not device.is_active:
                parser.error("El dispositivo existe con otro sensor o está inactivo; revisar antes de modificar")
            print("Dispositivo ya registrado: " + args.code)
        else:
            db.add(Device(device_code=args.code, sensor_type=args.sensor, name=args.name, location=args.location))
            print("Dispositivo registrado: " + args.code)


if __name__ == "__main__":
    main()
