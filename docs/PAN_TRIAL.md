# pan.tolvuhvislarinn.is — 14-day trial

Public demo/trial instance of Muninn for prospective shops.

## Setup

1. **DNS:** `pan.tolvuhvislarinn.is` → edge box (`100.79.10.104` or your public IP — same as `th.tolvuhvislarinn.is`).

2. **Deploy from Windows:**
   ```powershell
   .\deploy\deploy-pan.ps1
   ```
   Creates `/opt/pan-tolvuhvisl`, port **5003**, fresh DB, nginx, certbot, systemd.

3. **Trial expiry:** `.env` sets `TRIAL_EXPIRES_AT` to **14 days from first setup** (not overwritten on redeploy).

4. **SMTP:** Setup copies `SMTP_*` from `pantanir-tolvuhvisl` so **Komið** emails work. Without it, drag-to-Komið shows “SMTP ekki stillt”.

## Behaviour

- Banner on every page: days remaining
- After expiry: full-page “Prufutímabil lokið” (HTTP 403)
- **th.tolvuhvislarinn.is** unaffected (no `TRIAL_EXPIRES_AT` in its `.env`)

## Login (defaults)

| Role | Password |
|------|----------|
| Stjóri | `admin` |
| Notandi | `user` |

Set `STJORI_PASSWORD_HASH` / `NOTANDI_PASSWORD_HASH` in `/opt/pan-tolvuhvisl/.env` to change.

## Extend trial

On server:
```bash
# e.g. extend 14 more days from today
echo "TRIAL_EXPIRES_AT=$(date -d '+14 days' +%Y-%m-%d)" >> /opt/pan-tolvuhvisl/.env
sudo systemctl restart pan-tolvuhvisl
```

Or remove `TRIAL_EXPIRES_AT` to disable expiry (paid customer).

## Service

```bash
sudo systemctl status pan-tolvuhvisl
sudo journalctl -u pan-tolvuhvisl -f
```
