from typing import Protocol


class SecretProviderPort(Protocol):
    def get(self, key: str, default: str = "") -> str: ...
