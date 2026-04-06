#!/usr/bin/env bash
set -euo pipefail

echo "Removing generated artifacts from git index (non-destructive to working tree)."

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree has uncommitted changes. Please commit or stash before running this script." >&2
  exit 1
fi

removed=false
for p in build cloud_apps.egg-info .venv .env; do
  if git ls-files --error-unmatch "$p" > /dev/null 2>&1; then
    echo "Removing $p from git index"
    git rm -r --cached "$p" || true
    removed=true
  fi
done

# Ensure .gitignore contains entries
for g in .env .venv build/ cloud_apps.egg-info/; do
  if ! grep -qF "$g" .gitignore; then
    echo "$g" >> .gitignore
    git add .gitignore
  fi
done

if [ "$removed" = true ]; then
  git commit -m "Remove generated artifacts from repository index: build, .venv, cloud_apps.egg-info, .env"
  echo "Committed removal. You may need to push manually."
else
  echo "Nothing to remove from index."
fi
