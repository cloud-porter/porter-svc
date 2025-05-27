from pydantic.v1 import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Porter"
    app_version: str = "0.1.0"
    ak: str = ""
    sk: str = ""
    bucket_name: str = ""
    region_name: str = ""
    # class Config:
    #     env_file = ".env"


settings = Settings()