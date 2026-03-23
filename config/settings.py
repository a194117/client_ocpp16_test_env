# config/settings.py
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # General
    ws_url: str = Field("ws://localhost:8080/steve/websocket/CentralSystemService/", env="WS_URL")
    time_scale: int = Field(1, env="TIME_SCALE")
    recharge_value: float = Field(5.0, env="RECHARGE_VALUE")
    
    # Charge Point Attributes
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
    connectors_qty: int = Field(2, env="CONNECTORS_QTY")
    connector1_init_energy_import: float = Field(0.0, env="CONNECTOR1_INIT_ENERGY_IMPORT")
    connector2_init_energy_import: float = Field(0.0, env="CONNECTOR2_INIT_ENERGY_IMPORT")
    
    # Vehicle
    id_tag: str = Field("CARD123", env="ID_TAG")
    
    # Standard Measurements
    voltage: float = Field(370.0, env="VOLTAGE")
    current: float = Field(15.0, env="CURRENT")
    max_current: float = Field(200.0, env="MAX_CURRENT")
    frequency: float = Field(60.0, env="FREQUENCY")
    temperature: float = Field(305.0, env="TEMPERATURE")

    # Configuration Keys
    heartbeat_interval: int = Field(60, env="HEARTBEAT_INTERVAL")  
    connection_timeout: int = Field(30, env="CONNECTION_TIMEOUT") 
    reset_retries: int = Field(50, env="RESET_RETRIES")
    clock_aligned_data_interval: int = Field(900, env="CLOCK_ALIGNED_DATA_INTERVAL")
    meter_values_aligned_data: str | None = Field(None, env="METER_VALUES_ALIGNED_DATA")
    meter_values_sample_interval: int = Field(300, env="METER_VALUES_SAMPLE_INTERVAL")
    meter_values_sample_data: str | None = Field(None, env="METER_VALUES_SAMPLE_DATA")
    stop_txn_aligned_data: str | None = Field(None, env="STOP_TXN_ALIGNED_DATA")
    stop_txn_sample_data: str | None = Field(None, env="STOP_TXN_SAMPLE_DATA")
    
    # timeouts
    response_timeout: int = Field(30, env="RESPONSE_TIMEOUT")       

    # Retry / Backoff
    base_delay: float = Field(5.0, env="BASE_DELAY")                

    @field_validator("time_scale", mode="after")
    @classmethod
    def validate_time_scale(cls, v: int) -> int:
        if v < 1:
            # Você pode usar print ou um logger aqui
            logger.warning(f"AVISO: O valor de TIME_SCALE ({v}) no .env é inválido. Resetando para 1.")
            return 1
        return v
    
    @field_validator("meter_values_aligned_data", "meter_values_sample_data", "stop_txn_aligned_data", "stop_txn_sample_data",mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        # Se o valor for uma string vazia, retorna None
        if v == "":
            return None
        return v    
    

    class Config:
        env_file = "config/.env"
        env_file_encoding = "utf-8"

settings = Settings()