# config/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Websocket
    ws_url: str = Field("ws://localhost:8080/steve/websocket/CentralSystemService/", env="WS_URL")
    
    # Charge Point 
    station_id: str = Field("CP_1", env="STATION_ID")
    charge_point_model: str = Field("Annon_Model", env="CHARGE_POINT_MODEL")
    charge_point_vendor: str = Field("Annon_Vendor", env="CHARGE_POINT_VENDOR")
    charge_point_serial_number: str | None = Field(None, env="CHARGE_POINT_SERIAL_NUMBER")
    charge_box_serial_number: str | None = Field(None, env="CHARGE_BOX_SERIAL_NUMBER")
    firmware_version: str | None = Field(None, env="FIRMWARE_VERSION")
    iccid: str | None = Field(None, env="ICCID")
    imsi: str | None = Field(None, env="IMSI")
    meter_serial_number: str | None = Field(None, env="METER_SERIAL_NUMBER")
    meter_type: str | None = Field(None, env="METER_TYPE")
    
    # Connectors
    connectors_qty: int = Field(1, env="CONNECTORS_QTY")
    
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