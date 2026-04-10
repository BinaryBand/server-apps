import os

from src.ports import SecretProviderPort

_provider: SecretProviderPort | None = None


def _auto_detect() -> SecretProviderPort:
    vault_file = os.getenv("VAULT_FILE")
    if vault_file:
        from src.adapters.secrets.vault_provider import AnsibleVaultSecretProvider
        from src.infra.runtime import repo_root

        return AnsibleVaultSecretProvider(
            repo_root() / vault_file,
            password_file=os.getenv("VAULT_PASSWORD_FILE"),
            password=os.getenv("VAULT_PASSWORD"),
        )
    from src.adapters.secrets.env_provider import EnvironmentSecretProvider

    return EnvironmentSecretProvider()


def set_secret_provider(provider: SecretProviderPort) -> None:
    global _provider
    _provider = provider


def read_secret(name: str, default: str | None = None) -> str | None:
    global _provider
    if _provider is None:
        _provider = _auto_detect()
    result = _provider.get(name, "")
    return result or default


secret = read_secret  # backwards-compatible alias


def minio_credentials() -> tuple[str, str]:
    user = read_secret("MINIO_ROOT_USER") or read_secret("S3_ACCESS_KEY")
    password = read_secret("MINIO_ROOT_PASSWORD") or read_secret("S3_SECRET_KEY")
    if not user or not password:
        raise RuntimeError("Missing MinIO credentials")
    return user, password
