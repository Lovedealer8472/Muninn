# Muninn — engineering notes

*Internal structure and ops. No user-facing behaviour documented here.*

## Layout

```
app/
  app.py                 # Entry: create_app() + waitress __main__
  customer_email.py      # Email HTML/text templates
  muninn/
    __init__.py          # create_app() factory
    config.py            # Constants and feature flags
    db.py                  # SQLite schema, migrations, bootstrap
    auth.py                # Login decorators, role context
    logging_config.py      # LOG_LEVEL → Python logging
    routes/                # HTTP handlers (auth, board, orders, …)
    services/
      email.py             # SMTP dispatch, background queue
      orders.py            # Order logic, board queries, saga
  tests/                   # pytest (logic + smoke routes)
  .env.example
scripts/
  backup_db.sh             # sqlite3 .backup with timestamp
deploy/
  deploy-th.ps1            # scp + restart + HTTP smoke check
```

## Tests

```bash
cd app
pip install -r requirements.txt
python -m pytest tests/ -q
```

Uses a temporary SQLite DB (`TESTING=1`); does not touch production `pantanakerfi.db`.

## Logging

Set in `.env`:

```env
LOG_LEVEL=INFO   # DEBUG for request/SQL troubleshooting
```

## Database backup (server)

```bash
./scripts/backup_db.sh /opt/pantanir-tolvuhvisl
```

Keeps files in `app/backups/` (gitignored). Suggest daily cron on the edge box.

## Deploy

```powershell
.\deploy\deploy-th.ps1
```

Copies `app.py`, `customer_email.py`, `muninn/`, templates, static. Smoke-checks `https://th.tolvuhvislarinn.is/login`.

## Feature flags (rollback without code revert)

| Env | Default | Effect |
|-----|---------|--------|
| `PWA_ENABLED` | `1` | Installable app |
| `DETAIL_INLINE_EDIT` | `1` | Inline edit on detail; `0` restores **Breyta** button |
| `LOG_LEVEL` | `INFO` | Verbosity |

See also `docs/DETAIL_INLINE_EDIT.md`, `docs/PWA.md`.
