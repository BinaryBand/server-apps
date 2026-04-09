from pathlib import Path

import yaml
from ansible.constants import DEFAULT_VAULT_ID_MATCH
from ansible.parsing.vault import VaultLib, VaultSecret

from src.ports.secrets import SecretProviderPort


class AnsibleVaultSecretProvider(SecretProviderPort):
    """Reads secrets from an ansible-vault encrypted YAML file.

    Vault password source priority:
      1. password_file kwarg  (path to a plaintext file)
      2. password kwarg       (inline string, less secure)
    Vault data file: ansible/vault.yml (encrypted YAML key→value mapping).
    """

    def __init__(
        self,
        vault_file: Path,
        *,
        password_file: str | None = None,
        password: str | None = None,
    ) -> None:
        pw = self._load_password(password_file, password)
        vault_secret = VaultSecret(pw.encode())
        vault = VaultLib([(DEFAULT_VAULT_ID_MATCH, vault_secret)])
        decrypted = vault.decrypt(vault_file.read_bytes())
        self._data: dict[str, str] = yaml.safe_load(decrypted) or {}

    @staticmethod
    def _load_password(password_file: str | None, password: str | None) -> str:
        if password_file:
            return Path(password_file).read_text().strip()
        if password:
            return password
        raise RuntimeError("Ansible Vault requires VAULT_PASSWORD_FILE or VAULT_PASSWORD")

    def get(self, key: str, default: str = "") -> str:
        return self._data.get(key, default)
