# config/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Websocket
    ws_url: str = Field("ws://localhost:8080/steve/websocket/CentralSystemService/", env="WS_URL")
    
    # Charge Point 
    station_id: str = Field("CP_1", env="STATION_ID")
    connector_id: int = Field(1, env="CONNECTOR_ID")
    cp_model: str = Field("Optimus", env="CP_MODEL")
    cp_vendor: str = Field("The Mobility House", env="CP_VENDOR")
    
    # Vehicle
    id_tag: str = Field("CARD123", env="ID_TAG")

    # Heartbeat e timeouts
    heartbeat_interval: int = Field(60, env="HEARTBEAT_INTERVAL")   # segundos
    connection_timeout: int = Field(30, env="CONNECTION_TIMEOUT")   # segundos
    response_timeout: int = Field(30, env="RESPONSE_TIMEOUT")       # segundos

    # Retry / Backoff
    max_retries: int = Field(50, env="MAX_RETRIES")
    base_delay: float = Field(5.0, env="BASE_DELAY")                

    class Config:
        env_file = "config/.env"
        env_file_encoding = "utf-8"

settings = Settings()