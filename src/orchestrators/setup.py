from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from src.infra.locking import RunbookLock
from src.infra.runtime import locks_root, repo_root

REQUIRED_SECRETS = ["MINIO_ROOT_USER", "MINIO_ROOT_PASSWORD", "RESTIC_PASSWORD"]
_DEFAULT_VAULT_FILE = "ansible/vault.yml"
_DEFAULT_PW_FILE = ".vault-password"


def _vault_path() -> Path:
    raw = os.environ.get("VAULT_FILE", _DEFAULT_VAULT_FILE)
    p = Path(raw)
    return p if p.is_absolute() else repo_root() / p


def _pw_file_path() -> Path:
    raw = os.environ.get("VAULT_PASSWORD_FILE", _DEFAULT_PW_FILE)
    p = Path(raw)
    return p if p.is_absolute() else repo_root() / p


def _read_stored_password() -> str | None:
    if pw := os.environ.get("VAULT_PASSWORD"):
        return pw
    pw_file = _pw_file_path()
    if pw_file.exists():
        return pw_file.read_text(encoding="utf-8").strip()
    return None


def _get_vault_password() -> str:
    if pw := _read_stored_password():
        return pw
    if not sys.stdin.isatty():
        raise RuntimeError(
            "Vault password required but no TTY available. "
            "Set VAULT_PASSWORD or VAULT_PASSWORD_FILE, or run setup interactively."
        )
    pw = getpass.getpass("[setup] Vault password (new): ")
    pw_file = _pw_file_path()
    pw_file.write_text(pw + "\n", encoding="utf-8")
    pw_file.chmod(0o600)
    print(f"[setup] Password saved to {pw_file.relative_to(repo_root())}")
    return pw


def _load_vault_data(vault_file: Path, password: str) -> dict[str, str]:
    if not vault_file.exists():
        return {}
    from ansible.constants import DEFAULT_VAULT_ID_MATCH
    from ansible.parsing.vault import VaultLib, VaultSecret

    secret = VaultSecret(password.encode())
    vault = VaultLib([(DEFAULT_VAULT_ID_MATCH, secret)])
    return yaml.safe_load(vault.decrypt(vault_file.read_bytes())) or {}


def _write_vault(vault_file: Path, data: dict[str, str], password: str) -> None:
    from ansible.constants import DEFAULT_VAULT_ID_MATCH
    from ansible.parsing.vault import VaultLib, VaultSecret

    secret = VaultSecret(password.encode())
    vault = VaultLib([(DEFAULT_VAULT_ID_MATCH, secret)])
    plaintext = yaml.dump(data, default_flow_style=False)
    encrypted = vault.encrypt(plaintext, secret=secret)
    vault_file.parent.mkdir(parents=True, exist_ok=True)
    raw = encrypted if isinstance(encrypted, bytes) else encrypted.encode("utf-8")
    vault_file.write_bytes(raw)


def _missing_keys(data: dict[str, str]) -> list[str]:
    return [k for k in REQUIRED_SECRETS if not data.get(k)]


def _fill_from_env(data: dict[str, str], keys: list[str]) -> tuple[dict[str, str], list[str]]:
    from dotenv import dotenv_values

    env_file = repo_root() / ".env"
    env_values: dict = dotenv_values(env_file) if env_file.exists() else {}
    still_missing = []
    for key in keys:
        val = os.environ.get(key) or env_values.get(key)
        if val:
            data[key] = val
            print(f"[setup] Migrated {key} from env → vault")
        else:
            still_missing.append(key)
    return data, still_missing


def _fill_from_prompts(data: dict[str, str], keys: list[str]) -> dict[str, str]:
    if not sys.stdin.isatty():
        raise RuntimeError(
            f"Missing required secrets and no TTY available: {', '.join(keys)}. "
            "Run `python runbook/setup.py` interactively to populate the vault."
        )
    for key in keys:
        data[key] = getpass.getpass(f"[setup] Enter {key}: ")
    return data


def _activate_vault(vault_file: Path, password: str) -> None:
    from src.adapters.secrets.vault_provider import AnsibleVaultSecretProvider
    from src.infra.secrets import set_secret_provider

    set_secret_provider(AnsibleVaultSecretProvider(vault_file, password=password))


def ensure_secrets() -> None:
    """Pipeline stage: ensure all required secrets are present in the vault."""
    vault_file = _vault_path()
    password = _get_vault_password()
    data = _load_vault_data(vault_file, password)
    missing = _missing_keys(data)

    if missing:
        data, still_missing = _fill_from_env(data, missing)
        if still_missing:
            data = _fill_from_prompts(data, still_missing)
        _write_vault(vault_file, data, password)
        print(f"[setup] Vault written → {vault_file.relative_to(repo_root())}")

    _activate_vault(vault_file, password)


def main() -> None:
    with RunbookLock("setup", locks_root()):
        ensure_secrets()
    print("[setup] Done.")


if __name__ == "__main__":
    main()
