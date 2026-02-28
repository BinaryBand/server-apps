#!/bin/sh
set -e

# Create directories and set ownership using provided env vars
mkdir -p /etc/jellyfin /var/cache/jellyfin /var/lib/jellyfin
chown -R "${PUID:-1000}:${PGID:-1000}" /etc/jellyfin /var/cache/jellyfin /var/lib/jellyfin

# If additional command(s) were provided, run them; otherwise exit
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exit 0
