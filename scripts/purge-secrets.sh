#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
This helper shows safe steps to purge secrets (e.g. .env) from git history.

WARNING: History rewrite is destructive. Do NOT run this on a shared repo
without coordinating with all collaborators. Test on a fresh mirror clone first.

Two recommended tools:
- git-filter-repo (preferred): https://github.com/newren/git-filter-repo
- BFG Repo-Cleaner (alternative): https://rtyley.github.io/bfg-repo-cleaner/

Example workflow using git-filter-repo (manual, recommended):

1) Make a mirror backup of the repo (outside the repo directory):
   git clone --mirror /path/to/repo /tmp/repo-backup.git

2) Install git-filter-repo if needed:
   pip install --user git-filter-repo

3) In your working repo (ensure working tree is clean), run:
   # remove .env from all history
   git filter-repo --path .env --invert-paths --force

4) Inspect the repo and tags, then force-push to remote(s):
   git push --force --all
   git push --force --tags

Notes:
- This will rewrite all commits. Everyone using the repo will need to re-clone
  or follow their own recovery steps.
- If you need to remove multiple paths, provide multiple --path options or use
  --paths-from-file.

EOF

echo "Created instructions for secret purging. Read and run the steps manually."
