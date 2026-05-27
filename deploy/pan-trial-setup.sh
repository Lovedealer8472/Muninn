#!/usr/bin/env bash
# One-time server setup for pan.tolvuhvislarinn.is trial instance.
# Run on edge box as notandi (sudo available).
set -euo pipefail

APP_DIR="/opt/pan-tolvuhvisl"
SERVICE="pan-tolvuhvisl"
PORT=5003
DOMAIN="pan.tolvuhvislarinn.is"
NGINX_SITE="/etc/nginx/sites-available/${DOMAIN}"
EXPIRES=$(date -d "+14 days" +%Y-%m-%d)

echo "=== Muninn trial setup: ${DOMAIN} (expires ${EXPIRES}) ==="

sudo mkdir -p "${APP_DIR}"
sudo chown notandi:notandi "${APP_DIR}"

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
TRIAL_EXPIRES_AT=${EXPIRES}
TRACK_PUBLIC_URL=https://${DOMAIN}
SHOP_NAME=Muninn prufa
EOF
  chmod 600 "${APP_DIR}/.env"
  echo "Created ${APP_DIR}/.env (trial expires ${EXPIRES})"
else
  echo ".env exists — not overwriting"
fi

# Customer email (Komið status) — copy from TH if pan has no SMTP yet
if ! grep -q '^SMTP_SERVER=' "${APP_DIR}/.env" 2>/dev/null; then
  if [[ -f /opt/pantanir-tolvuhvisl/.env ]]; then
    grep '^SMTP' /opt/pantanir-tolvuhvisl/.env >> "${APP_DIR}/.env"
    echo "Copied SMTP settings from pantanir-tolvuhvisl"
  else
    echo "WARN: No SMTP on pan — set SMTP_* in ${APP_DIR}/.env for customer emails"
  fi
fi

sudo tee "/etc/systemd/system/${SERVICE}.service" > /dev/null <<EOF
[Unit]
Description=Muninn trial (${DOMAIN})
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

sudo systemctl reload nginx
sudo systemctl restart "${SERVICE}"
sleep 1
systemctl is-active "${SERVICE}"
curl -s -o /dev/null -w "Local HTTP: %{http_code}\n" "http://127.0.0.1:${PORT}/login"
echo "Done. Trial expires: ${EXPIRES}"
echo "Login: Stjóri/admin  Notandi/user (defaults unless .env hashes set)"
