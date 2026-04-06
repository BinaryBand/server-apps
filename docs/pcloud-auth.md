# pCloud Authentication (rclone)

This document explains how to obtain and install a pCloud access token for use with `rclone` in this project.

Summary
- Preferred runtime location for credentials: `rclone.conf` inside the Docker volume `rclone_config`.
- For local convenience, the helper `runbook/authorize_rclone.py` can obtain a token via `rclone authorize pcloud` and install it into the volume.
- Do NOT commit tokens into Git. Use `--export-env` only when you understand the risks.

Interactive flow (workstation)
1. On a machine with a browser and Docker (or rclone installed), run:

```bash
python runbook/authorize_rclone.py --install-volume
```

2. The helper will run `rclone authorize pcloud` (preferring local `rclone` then Docker), create a `rclone.conf`, and copy it into the `rclone_config` Docker volume with `0600` permissions.

Headless / server flow
- If the server has no browser, run the helper with `--headless` on a machine with a browser, or run `rclone authorize pcloud --auth-no-open-browser` on a separate workstation and paste the returned JSON into the helper using `--headless`.
- The helper supports `--install-volume` to place a usable `rclone.conf` into the Docker volume.

Exporting tokens into `.env` (optional)
- Use `--export-env` to write `PCLOUD_ACCESS_TOKEN` and `PCLOUD_EXPIRY` into the local `.env` file. The helper will ask for confirmation.
- Only use this for short-term convenience; prefer the Docker volume approach for runtime.

CI and automation
- Automation and CI should not rely on the interactive helper. Provide `PCLOUD_ACCESS_TOKEN` and `PCLOUD_EXPIRY` via secure CI secret injection or an external secrets manager.

Rotation and revocation
- Rotate tokens promptly if they are exposed. Revoke old tokens in pCloud and re-run the helper to install a fresh token.

Troubleshooting
- If the `rclone` container reports `unauthorized` or `401`, re-run the helper and ensure the `rclone_config` volume contains the new `rclone.conf`.
- To inspect the installed config from the host:

```bash
docker run --rm -v rclone_config:/config/rclone alpine:3.20 cat /config/rclone/rclone.conf
```

Security notes
- `rclone.conf` contains bearer tokens. Keep the Docker volume secure and avoid storing generated `rclone.conf` files in source control.
