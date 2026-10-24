from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./local.db"
    api_key: str
    csv_path: str = "./data/readings.csv"
    mqtt_host: str = "broker"
    mqtt_port: int = 1883
    mqtt_worker_username: str = "rutasalud-worker"
    mqtt_worker_password: str = ""


settings = Settings()
