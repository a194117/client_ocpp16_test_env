# cp_client/base.py
import logging
import os

from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger

from .context import connector_id, transaction_id


class ContextFilter(logging.Filter):
    """Adiciona campos fixos (station_id, connector_id) a todos os logs."""
    def __init__(self, station_id):
        super().__init__()
        self.station_id = station_id

    def filter(self, record):
        record.station_id = self.station_id
        record.connector_id = connector_id.get()
        record.transaction_id = transaction_id.get()
        return True

def setup_logger(name, log_to_console=False):
    """
    Configura um logger com saída para arquivo (e opcionalmente console).
    
    Args:
        name: Nome do logger.
        log_to_console: Se True, também envia logs para o console.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Remove handlers existentes
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Obtém o diretório raiz do projeto (dois níveis acima de base.py: base.py -> cp_client/ -> raiz)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"{name}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s %(station_id)s %(connector_id)s %(transaction_id)s'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    from config.settings import settings
    logger.addFilter(ContextFilter(settings.station_id))
    
    return logger