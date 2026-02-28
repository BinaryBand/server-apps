#!/bin/sh
set -e

TARGET=/config/rclone/rclone.conf

# Ensure the rclone config is a file (not a mis-mounted directory)
if [ -d "$TARGET" ]; then
  echo "ERROR: $TARGET is a directory (incorrect mount). Mount a file or a directory containing rclone.conf at /config/rclone." >&2
  exit 1
fi

# Unmount stale mount, create mountpoint, then exec rclone mount
(umount -l /media/pcloud/Media 2>/dev/null || true)
mkdir -p /media/pcloud/Media

# render rclone.conf from template if present and target missing
TEMPLATE=/config/rclone/rclone.template.conf

if [ -f "$TEMPLATE" ] && [ ! -f "$TARGET" ]; then
  echo "Rendering rclone config from template"
  envsubst < "$TEMPLATE" > "$TARGET"
  chmod 600 "$TARGET"
fi

exec rclone mount "${RCLONE_REMOTE:-pcloud}:Media" /media/pcloud/Media \
  --allow-other --vfs-cache-mode writes --vfs-cache-max-size 5G --vfs-cache-max-age 12h \
  --read-only \
  --uid "${PUID:-1000}" --gid "${MEDIA_GID:-3000}" --umask 027 \
  --log-file /logs/media.log --log-level DEBUG
