# store/conf_keys.py
"""
Estrutura de dados para gerenciar as chaves de configuração (configuration keys)
do Charge Point virtual, com suporte a thread-safe via BaseLockedState.
"""
from dataclasses import dataclass
from typing import Any, Dict, Type

from store.base import BaseLockedState, locked
from config.settings import settings
from store.key_definitions import KEY_DEFS 


@dataclass
class ConfigKey:
    name: str
    value: Any
    accessibility: str
    type: Type


class ConfigurationKeys(BaseLockedState):
    """
    Gerencia as chaves de configuração do Charge Point.
    As definições das chaves estão em key_definitions.KEY_DEFS.
    """

    # Mapeamento entre nomes de chave OCPP e atributos do settings (quando houver)
    _SETTINGS_ATTR_MAP: Dict[str, str] = {
        "NumberOfConnectors": "connectors_qty",
        "HeartbeatInterval": "heartbeat_interval",
        "ConnectionTimeOut": "connection_timeout",
        "ResetRetries": "reset_retries",
        "ClockAlignedDataInterval": "clock_aligned_data_interval",
        "MeterValuesAlignedData": "meter_values_aligned_data",
        "MeterValueSampleInterval": "meter_values_sample_interval",
        "MeterValuesSampledData": "meter_values_sample_data",
        "StopTxnAlignedData": "stop_txn_aligned_data",
        "StopTxnSampledData": "stop_txn_sample_data",
    
        # Adicione outros mapeamentos se necessário
    }

    def __init__(self):
        super().__init__()  # inicializa _lock e _allow_write

        # Percorre todas as definições carregadas do arquivo externo
        for key_name, (access, typ, default) in KEY_DEFS.items():
            # Verifica se a chave tem valor vindo do settings
            settings_attr = self._SETTINGS_ATTR_MAP.get(key_name)
            if settings_attr and hasattr(settings, settings_attr):
                value = getattr(settings, settings_attr)
                if value is None:
                    pass  # value continua None
                # Garante que o valor é do tipo esperado
                elif not isinstance(value, typ):
                    try:
                        value = typ(value)
                    except (ValueError, TypeError):
                        value = default
            else:
                value = default

            # Cria o objeto ConfigKey e o armazena como atributo
            setattr(self, key_name, ConfigKey(
                name=key_name,
                value=value,
                accessibility=access,
                type=typ
            ))

    @locked
    def get(self, key: str) -> Any:
        if not hasattr(self, key):
            raise AttributeError(f"Chave de configuração '{key}' não existe.")
        return getattr(self, key).value

    @locked
    def set(self, key: str, value: Any) -> None:
        if not hasattr(self, key):
            raise AttributeError(f"Chave de configuração '{key}' não existe.")
        key_obj = getattr(self, key)
        if key_obj.accessibility != "RW":
            raise AttributeError(f"A chave '{key}' é somente leitura e não pode ser modificada.")
        if not isinstance(value, key_obj.type):
            try:
                value = key_obj.type(value)
            except (ValueError, TypeError):
                raise TypeError(
                    f"Valor para chave '{key}' deve ser do tipo {key_obj.type.__name__}, "
                    f"recebido {type(value).__name__}."
                )
        key_obj.value = value

    def list_keys(self) -> Dict[str, ConfigKey]:
        return {
            name: getattr(self, name)
            for name in dir(self)
            if isinstance(getattr(self, name), ConfigKey)
        }


# Instância global para ser usada em toda a aplicação
configuration_keys = ConfigurationKeys()