#!/usr/bin/env bash
# Server setup for demo.tolvuhvislarinn.is (public sandbox).
set -euo pipefail

APP_DIR="/opt/demo-tolvuhvisl"
SERVICE="demo-tolvuhvisl"
PORT=5004
DOMAIN="demo.tolvuhvislarinn.is"
NGINX_SITE="/etc/nginx/sites-available/${DOMAIN}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Muninn demo setup: ${DOMAIN} ==="

sudo mkdir -p "${APP_DIR}/scripts"
sudo chown -R notandi:notandi "${APP_DIR}"

if [[ ! -d "${APP_DIR}/venv" ]]; then
  echo "Creating venv..."
  python3 -m venv "${APP_DIR}/venv"
fi
if [[ -f "${APP_DIR}/requirements.txt" ]]; then
  "${APP_DIR}/venv/bin/pip" install -q -r "${APP_DIR}/requirements.txt"
fi

if [[ ! -f "${APP_DIR}/.env" ]]; then
  SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
  cat > "${APP_DIR}/.env" <<EOF
SECRET_KEY=${SECRET}
LOG_LEVEL=INFO
FLASK_HOST=127.0.0.1
FLASK_PORT=${PORT}
FLASK_DEBUG=0
BEHIND_PROXY=1
PWA_ENABLED=1
DETAIL_INLINE_EDIT=1
DEMO_MODE=1
TRACK_PUBLIC_URL=https://${DOMAIN}
SHOP_NAME=Muninn — prufuvistun
EOF
  chmod 600 "${APP_DIR}/.env"
  echo "Created ${APP_DIR}/.env (demo mode, no SMTP)"
else
  echo ".env exists — not overwriting"
  if ! grep -q '^DEMO_MODE=' "${APP_DIR}/.env"; then
    echo "DEMO_MODE=1" >> "${APP_DIR}/.env"
  fi
fi

# Seed database (no real customer data)
if [[ -f "${APP_DIR}/scripts/seed_demo_db.py" ]]; then
  "${APP_DIR}/venv/bin/python" "${APP_DIR}/scripts/seed_demo_db.py" \
    "${APP_DIR}/pantanakerfi.db" \
    --seed-copy "${APP_DIR}/pantanakerfi.db.seed"
else
  echo "WARN: seed_demo_db.py not deployed yet — run deploy-demo.ps1 first"
fi

cp -f "${SCRIPT_DIR}/../scripts/reset_demo_db.sh" "${APP_DIR}/scripts/reset_demo_db.sh" 2>/dev/null || \
  cp -f /tmp/reset_demo_db.sh "${APP_DIR}/scripts/reset_demo_db.sh" 2>/dev/null || true
chmod +x "${APP_DIR}/scripts/reset_demo_db.sh" 2>/dev/null || true

sudo tee "/etc/systemd/system/${SERVICE}.service" > /dev/null <<EOF
[Unit]
Description=Muninn public demo (${DOMAIN})
After=network.target

[Service]
Type=simple
User=notandi
Group=notandi
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/venv/bin/python ${APP_DIR}/app.py
Restart=always
RestartSec=5
Environment=LANG=en_US.UTF-8

[Install]
WantedBy=multi-user.target
EOF

sudo tee "${NGINX_SITE}" > /dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 30m;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf "${NGINX_SITE}" "/etc/nginx/sites-enabled/${DOMAIN}"
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE}"

if [[ ! -d "/etc/letsencrypt/live/${DOMAIN}" ]]; then
  echo "Requesting TLS certificate (DNS must point here first)..."
  sudo certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m tolvuhvislarinn@tolvuhvislarinn.is || {
    echo "Certbot failed — check DNS for ${DOMAIN}, then run:"
    echo "  sudo certbot --nginx -d ${DOMAIN}"
  }
else
  echo "TLS cert already present"
fi

# Weekly reset — Sunday 03:00
CRON_LINE="0 3 * * 0 ${APP_DIR}/scripts/reset_demo_db.sh >> /tmp/muninn-demo-reset.log 2>&1"
( crontab -l 2>/dev/null | grep -v 'reset_demo_db.sh' || true; echo "${CRON_LINE}" ) | crontab -
echo "Cron: weekly demo DB reset (Sun 03:00)"

sudo systemctl reload nginx
sudo systemctl restart "${SERVICE}"
sleep 1
systemctl is-active "${SERVICE}"
curl -s -o /dev/null -w "Local HTTP: %{http_code}\n" "http://127.0.0.1:${PORT}/login"
echo "Done. Login: Stjóri/admin  Notandi/user"
