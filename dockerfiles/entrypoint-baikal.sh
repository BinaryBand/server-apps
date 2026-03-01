# Also prepare Baikal directories if present in the compose setup
mkdir -p /var/www/baikal/config /var/www/baikal/Specific
chown -R "${PUID:-1000}:${PGID:-1000}" /etc/jellyfin /var/cache/jellyfin /var/lib/jellyfin /var/www/baikal