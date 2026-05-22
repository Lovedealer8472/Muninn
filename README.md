# Muninn

Order-tracking board for small shops (Icelandic workflow). Flask + SQLite + Waitress.

## Repository layout

| Path | Purpose |
|------|---------|
| `app/` | Application source (`app.py`, `templates/`, `static/`) |
| `docs/` | Project status, backlog, deploy notes |
| `deploy/` | Scripts to push to servers |

## Live instances

| Host | Path on server | URL | Notes |
|------|----------------|-----|-------|
| **TH (dev/Muninn UI)** | `/opt/pantanir-tolvuhvisl` | `th.tolvuhvislarinn.is` | Primary development target |
| Pantanakerfi (prod store) | `/opt/pantanakerfi` | `pantanakerfi.tolvuhvislarinn.is` | Deploy only when explicitly requested |

## Quick start (local)

```bash
cd app
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # create from template if present
python app.py              # or waitress per README in app/
```

## Deploy to TH

From Windows (OpenClaw workspace):

```powershell
.\deploy\deploy-th.ps1
```

Or manually: copy `app/*` to `notandi@100.79.10.104:/opt/pantanir-tolvuhvisl/` and `sudo systemctl restart pantanir-tolvuhvisl`.

## Docs

- [Project status](docs/PROJECT_STATUS.md)
- [Backlog](docs/BACKLOG.md)
