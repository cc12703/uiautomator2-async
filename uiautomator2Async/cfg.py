





from typing import Any


class Config(object) :


    def __init__(self) -> None:

        self._defaults = {
            "wait_timeout": 20.0,
            "reset_adb_wifi_addr": None,
            "reset_atx_listen_addr": None
        }


    def __setitem__(self, key: str, val: Any):
        if key not in self._defaults:
            raise RuntimeError("invalid key", key)
        
        self._defaults[key] = val

    def __getitem__(self, key: str) -> Any:
        if key not in self._defaults:
            raise RuntimeError("invalid key", key)
        return self._defaults.get(key)
