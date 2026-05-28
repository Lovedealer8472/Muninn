# demo.tolvuhvislarinn.is — public sandbox

Permanent live demo linked from [tolvuhvislarinn.is/verkefni](https://www.tolvuhvislarinn.is/projects).

## Purpose

| Instance | URL | Use |
|----------|-----|-----|
| **demo** | demo.tolvuhvislarinn.is | Site visitors — fictional data, weekly reset |
| **pan** | pan.tolvuhvislarinn.is | Per-shop sales trials (14-day expiry) |
| **th** | th.tolvuhvislarinn.is | Internal dev / dogfood |

## Setup

1. DNS: `demo.tolvuhvislarinn.is` → edge box (same A as `th` / `pan`).

2. Deploy from Windows:
   ```powershell
   .\deploy\deploy-demo.ps1
   ```

3. Server path: `/opt/demo-tolvuhvisl`, port **5004**, service `demo-tolvuhvisl`.

## Behaviour

- `DEMO_MODE=1` — green banner with login hint (Stjóri/admin, Notandi/user)
- **No** `TRIAL_EXPIRES_AT` — never shows trial expiry wall
- **No SMTP** — visitors cannot send real customer emails
- **Fictional seed data** only (`@example.is` addresses, Demo/Prufu names)
- **Weekly reset** — cron Sunday 03:00 runs `scripts/reset_demo_db.sh`

## Manual reset

```bash
/opt/demo-tolvuhvisl/scripts/reset_demo_db.sh
```

## Reseed from scratch

```bash
cd /opt/demo-tolvuhvisl
venv/bin/python scripts/seed_demo_db.py pantanakerfi.db --seed-copy pantanakerfi.db.seed
sudo systemctl restart demo-tolvuhvisl
```

## Login (defaults)

| Role | Password |
|------|----------|
| Stjóri | `admin` |
| Notandi | `user` |

Credentials are shown in the demo banner — this is intentional for a public sandbox.
