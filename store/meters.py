# store/meters.py
import threading
from typing import Dict, List, Optional, Set, Union

from ocpp.v16 import enums
from ocpp.v16.datatypes import MeterValue, SampledValue

from store.base import BaseLockedState, locked

from config.settings import settings

# Mapeamento de measurand para unidade padrão (conforme OCPP 1.6)
MEASURAND_UNITS: Dict[enums.Measurand, Optional[enums.UnitOfMeasure]] = {
    enums.Measurand.energy_active_export_register: enums.UnitOfMeasure.wh,
    enums.Measurand.energy_active_import_register: enums.UnitOfMeasure.wh,
    enums.Measurand.energy_reactive_export_register: enums.UnitOfMeasure.varh,
    enums.Measurand.energy_reactive_import_register: enums.UnitOfMeasure.varh,
    enums.Measurand.energy_active_export_interval: enums.UnitOfMeasure.wh,
    enums.Measurand.energy_active_import_interval: enums.UnitOfMeasure.wh,
    enums.Measurand.energy_reactive_export_interval: enums.UnitOfMeasure.varh,
    enums.Measurand.energy_reactive_import_interval: enums.UnitOfMeasure.varh,
    enums.Measurand.power_active_export: enums.UnitOfMeasure.w,
    enums.Measurand.power_active_import: enums.UnitOfMeasure.w,
    enums.Measurand.power_offered: enums.UnitOfMeasure.w,
    enums.Measurand.power_reactive_export: enums.UnitOfMeasure.var,
    enums.Measurand.power_reactive_import: enums.UnitOfMeasure.var,
    enums.Measurand.power_factor: None,          # adimensional
    enums.Measurand.current_import: enums.UnitOfMeasure.a,
    enums.Measurand.current_export: enums.UnitOfMeasure.a,
    enums.Measurand.current_offered: enums.UnitOfMeasure.a,
    enums.Measurand.voltage: enums.UnitOfMeasure.v,
    enums.Measurand.frequency: None,             # Hz (não definido no padrão)
    enums.Measurand.temperature: enums.UnitOfMeasure.celsius,
    enums.Measurand.soc: enums.UnitOfMeasure.percent,
    enums.Measurand.rpm: None,                   # rotações por minuto
}


class Meters(BaseLockedState):
    """
    Gerencia os valores dos medidores (Measurand) para os conectores 1, 2 e 0 (charge point).
    O conector 0 tem seus valores calculados conforme regras, para manter consistência dos dados:
    - Soma: para a maioria
    - Máximo: Power.Factor, Current.Import, Current.Export, Current.Offered, SoC
    - Igual (valor global): Voltage, Frequency, Temperature, RPM
    Thread-safe, herdando o mecanismo de lock de BaseLockedState.
    """

    # Conjuntos de measurands com regras especiais
    _MAX_MEASURANDS: Set[enums.Measurand] = {
        enums.Measurand.power_factor,
        enums.Measurand.current_import,
        enums.Measurand.current_export,
        enums.Measurand.current_offered,
        enums.Measurand.soc,
    }

    _GLOBAL_MEASURANDS: Set[enums.Measurand] = {
        enums.Measurand.voltage,
        enums.Measurand.frequency,
        enums.Measurand.temperature,
        enums.Measurand.rpm,
    }

    def __init__(self) -> None:
        super().__init__()
        # Armazena dados dos conectores físicos (1 e 2)
        self._data: Dict[int, Dict[enums.Measurand, float]] = {
            1: {m: 0.0 for m in enums.Measurand},
            2: {m: 0.0 for m in enums.Measurand},
        }
        # Armazena valores globais para measurands que são iguais para todos os conectores
        self._global_values: Dict[enums.Measurand, float] = {
            m: 0.0 for m in self._GLOBAL_MEASURANDS
        }
        
    @locked
    def initialize_from_settings(self, settings) -> None:
        """
        Inicializa os medidores com valores do módulo de configuração.
        """
        
        voltage = float(settings.voltage)
        frequency = float(settings.frequency)
        temperature = float(settings.temperature)
        max_current = float(settings.max_current)
        energy1 = float(settings.connector1_init_energy_import)
        energy2 = float(settings.connector2_init_energy_import)

        # Temperature (global)
        self._global_values[enums.Measurand.temperature] = temperature
        self._data[1][enums.Measurand.temperature] = temperature
        self._data[2][enums.Measurand.temperature] = temperature
        
        # Frequency (global)
        self._global_values[enums.Measurand.frequency] = frequency
        self._data[1][enums.Measurand.frequency] = frequency
        self._data[2][enums.Measurand.frequency] = frequency


        # Voltage (global)
        self._global_values[enums.Measurand.voltage] = voltage
        self._data[1][enums.Measurand.voltage] = voltage
        self._data[2][enums.Measurand.voltage] = voltage


        # Current.Offered (por conector)
        self._data[1][enums.Measurand.current_offered] = max_current
        self._data[2][enums.Measurand.current_offered] = max_current

        # Power.Offered (por conector)
        power_offered = max_current * voltage
        self._data[1][enums.Measurand.power_offered] = power_offered
        self._data[2][enums.Measurand.power_offered] = power_offered

        # Energia importada inicial
        self._data[1][enums.Measurand.energy_active_import_register] = energy1
        self._data[2][enums.Measurand.energy_active_import_register] = energy2

    def _get_raw_value(self, connector_id: int, measurand: enums.Measurand) -> float:
        """
        Retorna o valor float bruto para um conector e measurand (sem lock).
        Para conector 0, aplica as regras de cálculo.
        """
        if connector_id == 0:
            if measurand in self._GLOBAL_MEASURANDS:
                return self._global_values[measurand]
            elif measurand in self._MAX_MEASURANDS:
                return max(self._data[1][measurand], self._data[2][measurand])
            else:
                return self._data[1][measurand] + self._data[2][measurand]
        else:
            return self._data[connector_id][measurand]

    def get_value(
        self,
        connector_id: int,
        measurand: Optional[enums.Measurand] = None,
    ) -> str:
        """
        Retorna o valor de um medidor como string.
        Se measurand for None, usa Energy.Active.Import.Register.
        Para connector_id == 0, aplica as regras de cálculo.
        """
        if connector_id not in (0, 1, 2):
            raise ValueError("connector_id deve ser 0, 1 ou 2")

        if measurand is None:
            measurand = enums.Measurand.energy_active_import_register

        with self._lock:
            value = self._get_raw_value(connector_id, measurand)
            return str(value)

    @locked
    def set_value(
        self,
        connector_id: int,
        measurand: enums.Measurand,
        value: Union[float, str],
    ) -> None:
        """
        Define o valor de um medidor.
        - Para connector_id 1 ou 2:
            - Se measurand for global (Voltage, Frequency, Temperature, RPM), o valor é armazenado
              globalmente e também replicado para ambos os conectores.
            - Caso contrário, armazena apenas no conector especificado.
        - Para connector_id 0: não é permitido (valores são calculados).
        """
        if connector_id == 0:
            raise ValueError("Não é possível definir valor diretamente para o conector 0")
        if connector_id not in (1, 2):
            raise ValueError("connector_id deve ser 1 ou 2 para set_value")

        float_val = float(value)

        if measurand in self._GLOBAL_MEASURANDS:
            self._global_values[measurand] = float_val
            self._data[1][measurand] = float_val
            self._data[2][measurand] = float_val
        else:
            self._data[connector_id][measurand] = float_val

    @locked
    def update_values(
        self,
        connector_id: int,
        values: Dict[enums.Measurand, Union[float, str]],
    ) -> None:
        """
        Atualiza múltiplos medidores de um conector de forma atômica.
        Aplica as mesmas regras de set_value.
        """
        if connector_id == 0:
            raise ValueError("Não é possível atualizar valores para o conector 0")
        if connector_id not in (1, 2):
            raise ValueError("connector_id deve ser 1 ou 2 para update_values")

        for measurand, val in values.items():
            float_val = float(val)
            if measurand in self._GLOBAL_MEASURANDS:
                self._global_values[measurand] = float_val
                self._data[1][measurand] = float_val
                self._data[2][measurand] = float_val
            else:
                self._data[connector_id][measurand] = float_val

    def get_meter_value(
        self,
        connector_id: int,
        measurands: Optional[List[enums.Measurand]] = None,
        context: Optional[enums.ReadingContext] = None,
        phase: Optional[enums.Phase] = None,
        location: Optional[enums.Location] = None,
    ) -> List[Dict[str, any]]:
        """
        Retorna um vetor de objetos objetos sampledValue com os valores atuais.
        Se measurands for None, inclui todos os medidores.
        Os parâmetros context, phase, location são aplicados a todos os sampled values,
        a menos que sejam None (então não incluídos).
        """
        if connector_id not in (0, 1, 2):
            raise ValueError("connector_id deve ser 0, 1 ou 2")

        if measurands is None:
            measurands = [enums.Measurand.energy_active_import_register]

        sampled_dicts = []
        with self._lock:
            for m in measurands:
                value = self._get_raw_value(connector_id, m)
                unit = MEASURAND_UNITS.get(m)

                # Monta o dicionário básico com o campo obrigatório 'value'
                sampled_dict = {
                    "value": str(value),
                }

                # Adiciona campos opcionais apenas se não forem None
                if m is not None:
                    sampled_dict["measurand"] = m.value
                if unit is not None:
                    sampled_dict["unit"] = unit.value
                if context is not None:
                    sampled_dict["context"] = context.value
                if phase is not None:
                    sampled_dict["phase"] = phase.value
                if location is not None:
                    sampled_dict["location"] = location.value
                # O campo 'format' não é usado aqui, mas se houver, trate similarmente

                sampled_dicts.append(sampled_dict)

        return sampled_dicts

# Criamos uma única instância global deste estado e Inicializa com as configurações
meters = Meters()
meters.initialize_from_settings(settings)
