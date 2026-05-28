#!/usr/bin/env bash
# Reset demo.tolvuhvislarinn.is to seeded fictional data.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/demo-tolvuhvisl}"
SERVICE="${SERVICE:-demo-tolvuhvisl}"
SEED="${APP_DIR}/pantanakerfi.db.seed"
DB="${APP_DIR}/pantanakerfi.db"

if [[ ! -f "${SEED}" ]]; then
  echo "Missing seed file: ${SEED}" >&2
  exit 1
fi

cp "${SEED}" "${DB}"
sudo systemctl restart "${SERVICE}"
echo "Demo DB reset from ${SEED} and ${SERVICE} restarted."
