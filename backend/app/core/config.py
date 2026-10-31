from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./local.db"
    api_key: str
    csv_path: str = "./data/readings.csv"


settings = Settings()
