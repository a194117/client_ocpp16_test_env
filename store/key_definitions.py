# store/key_definitions.py
"""
Definições de todas as chaves de configuração OCPP 1.6.
Cada entrada é uma tupla: (acessibilidade, tipo, valor_padrão)
Onde acessibilidade = "RW" (leitura/escrita) ou "RO" (somente leitura).

*   Valores definidos como DEFAULT poderão ser sobrescritos se a chave estiver sendo definida no config/settings.py
"""
KEY_DEFS = {
    # Core Profile (34 keys)
    "AllowOfflineTxForUnknownId": ("RW", bool, False),
    "AuthorizationCacheEnabled": ("RW", bool, False),
    "AuthorizeRemoteTxRequests": ("RW", bool, False),
    "BlinkRepeat": ("RW", int, 0),
    "ClockAlignedDataInterval": ("RW", int, 900),
    "ConnectionTimeOut": ("RW", int, 30),          
    "ConnectorPhaseRotation": ("RW", str, ""),     
    "ConnectorPhaseRotationMaxLength": ("RO", int, 0),
    "GetConfigurationMaxKeys": ("RO", int, 0),
    "HeartbeatInterval": ("RW", int, 60),           
    "LightIntensity": ("RW", int, 0),
    "LocalAuthorizeOffline": ("RW", bool, False),
    "LocalPreAuthorize": ("RW", bool, False),
    "MaxEnergyOnInvalidId": ("RW", int, 0),
    "MeterValuesAlignedData": ("RW", str, ""),      
    "MeterValuesAlignedDataMaxLength": ("RO", int, 0),
    "MeterValuesSampledData": ("RW", str, ""),      
    "MeterValuesSampledDataMaxLength": ("RO", int, 0),
    "MeterValueSampleInterval": ("RW", int, 300),
    "MinimumStatusDuration": ("RW", int, 0),
    "NumberOfConnectors": ("RO", int, 2),
    "ResetRetries": ("RW", int, 0),
    "StopTransactionOnEVSideDisconnect": ("RW", bool, False),
    "StopTransactionOnInvalidId": ("RW", bool, False),
    "StopTxnAlignedData": ("RW", str, ""),          
    "StopTxnAlignedDataMaxLength": ("RO", int, 0),
    "StopTxnSampledData": ("RW", str, ""),          
    "StopTxnSampledDataMaxLength": ("RO", int, 0),
    "SupportedFeatureProfiles": ("RO", str, ""),    
    "SupportedFeatureProfilesMaxLength": ("RO", int, 0),
    "TransactionMessageAttempts": ("RW", int, 0),
    "TransactionMessageRetryInterval": ("RW", int, 0),
    "UnlockConnectorOnEVSideDisconnect": ("RW", bool, False),
    "WebSocketPingInterval": ("RW", int, 0),

    # Local Auth List Management Profile (3 keys)
    "LocalAuthListEnabled": ("RW", bool, False),
    "LocalAuthListMaxLength": ("RO", int, 0),
    "SendLocalListMaxLength": ("RO", int, 0),

    # Reservation Profile (1 key)
    "ReserveConnectorZeroSupported": ("RO", bool, False),

    # Smart Charging Profile (5 keys)
    "ChargeProfileMaxStackLevel": ("RO", int, 0),
    "ChargingScheduleAllowedChargingRateUnit": ("RO", str, ""),  
    "ChargingScheduleMaxPeriods": ("RO", int, 0),
    "ConnectorSwitch3to1PhaseSupported": ("RO", bool, False),
    "MaxChargingProfilesInstalled": ("RO", int, 0),
}