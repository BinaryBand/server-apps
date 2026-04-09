import os
import sys

from dotenv import find_dotenv, load_dotenv

from src.ports.secrets import SecretProviderPort


class EnvironmentSecretProvider(SecretProviderPort):
    def __init__(self) -> None:
        if "PYTEST_CURRENT_TEST" not in os.environ and "pytest" not in sys.modules:
            load_dotenv(find_dotenv())

    def get(self, key: str, default: str = "") -> str:
        return os.getenv(key, default)
