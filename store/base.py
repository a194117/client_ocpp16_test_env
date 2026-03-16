import threading
from functools import wraps
from typing import Any, Callable

def locked(func):
    """
    decorador personalizado que envolve uma função para adquirir o lock antes de executá-la.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            # Ativamos uma "bandeira" interna para permitir a escrita temporariamente
            self._allow_write = True
            try:
                return func(self, *args, **kwargs)
            finally:
                self._allow_write = False
    return wrapper

class BaseLockedState:
    """
    Classe base para objetos de estado que requerem acesso thread-safe. 
    Fornece um mecanismo de bloqueio e proteção contra gravação. 
    As subclasses devem chamar `super().__init__()` para inicializar o bloqueio e o sinalizador.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._allow_write = False

    def __setattr__(self, name: str, value: Any) -> None:
        # 1. Permitir a criação dos atributos de controle e enquanto _lock não existe
        if name in ('_lock', '_allow_write') or not hasattr(self, '_lock'):
            super().__setattr__(name, value)
            return

        # 2. Se o atributo ainda não existe, permitir sua criação (inicialização)
        if not hasattr(self, name):
            super().__setattr__(name, value)
            return

        # 3. Para atributos já existentes, exigir _allow_write
        if not self._allow_write:
            raise AttributeError(
                f"Não é permitido modificar '{name}' diretamente. Use o método update()."
            )
        
        super().__setattr__(name, value)

    @locked
    def update(self, **kwargs) -> None:
        """
        Método genérico de atualização para alterar vários atributos de uma só vez. 
        Funciona apenas para atributos que já existem.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"O atributo '{key}' nao existe.")

    @locked
    def reset(self) -> None:
        """
        Reset Dinâmico da Classe. 
        Percorre todos os campos da classe e atribui a eles o valor de uma nova instância "limpa". 
        """
        default_instance = self.__class__()
        
        for attr_name in self.__dict__:
            if attr_name in ('_lock', '_allow_write'):
                continue
                
            default_value = getattr(default_instance, attr_name)
            setattr(self, attr_name, default_value)