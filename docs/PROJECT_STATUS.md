# Muninn — project status

*Last updated: 2026-05-26*

## Product

Muninn is a lightweight **special-order / repair tracking** tool: kanban board, order detail, **auto customer email on Komið**, manual **Email** button for other updates, public tracking by phone, attachments, comments, soft-delete trash (30 days).

**Primary deploy target:** `th.tolvuhvislarinn.is` (`/opt/pantanir-tolvuhvisl` on edge `100.79.10.104`).

**Trial / demo:** `pan.tolvuhvislarinn.is` (`/opt/pan-tolvuhvisl`, port 5003, 14-day `TRIAL_EXPIRES_AT`).

**Not in scope unless asked:** `pantanakerfi.tolvuhvislarinn.is` (production Pantanakerfi branding).

**Evolution history:** [EVOLUTION.md](EVOLUTION.md)

## Status pipeline

`Móttekið` → `Í vinnslu` → `Pantað` → `Staðfest` → `Komið` → `Lokið`

## Features shipped (TH)

| Area | Status |
|------|--------|
| Muninn branding (board, detail, forms) | Live |
| Print order | Live |
| Order comments (Ummæli) + saga | Live |
| Færa áfram modal + optional email | Live |
| Email send in background thread (no UI freeze) | Live |
| Soft delete + Rusl (30-day retention) | Live |
| Trash icon in header | Live |
| **Tier 1 board UX** (2026-05-22) | Live on TH |
| **Tier 2 Wave A** (2026-05-22) | Live on TH — stale filter, comment badges, email result banner |
| **Board drag-and-drop** (2026-05-22) | Live — drag handle on cards; Stjóri any column, Notandi next step only |
| **Stjóri / Notandi roles** (2026-05-22) | Live on TH — `admin` / `user` per role at login |
| **Inline detail edit** (`DETAIL_INLINE_EDIT`) | Live — rollback via env |
| **14-day trial** (`pan.tolvuhvislarinn.is`) | Live — `TRIAL_EXPIRES_AT`, expiry banner/page |
| **Package refactor** (`app/muninn/`) | Live — pytest, logging, `.env.example` |
| **Icelandic email rewrite** (2026-05-26) | Live on TH + pan |

### Tier 1 (clerk / owner feedback)

1. Overdue + idle-day badges on board cards  
2. Contact status on cards  
3. Komið highlighted (“Til afhendingar”)  
4. Search placeholder + phone-digit search  
5. Status legend info modal (header **Stöður** button)  
6. Lokið clarified as “(afhent)” on detail pipeline  
7. After status change from board dropdown → return to **order detail** (modal path already on detail)

## Infrastructure

- **Service:** `pantanir-tolvuhvisl.service` (port 5001)  
- **DB:** `app/pantanakerfi.db` (SQLite, WAL)  
- **SMTP:** Migadu via `.env` on server  
- **Code:** `app/muninn/` package (refactored from monolithic `app.py`)  
- **Tests:** `cd app && python -m pytest tests/` (19+ tests)  
- **Logging:** `LOG_LEVEL=INFO` in `.env` (`DEBUG` for per-request traces)  
- **Backup:** `scripts/backup_db.sh /opt/pantanir-tolvuhvisl`  
- **Engineering docs:** [ENGINEERING.md](ENGINEERING.md)

## Roles (Stjóri / Notandi)

| | **Notandi** | **Stjóri** |
|---|-------------|------------|
| Board, search, new order | Yes | Yes |
| Færa áfram (one click, auto email at Komið) | Yes (next step only) | Yes |
| Email (manual, current status) | Yes | Yes |
| Breyta, Ummæli, QR, Prenta | Yes | Yes |
| Status dropdown on cards | No | No (drag-and-drop) |
| Eyða / Rusl | No | Yes |
| Geyma (Lokið + Greitt) | Yes | Yes |
| Tölfræði | No | Yes |

Separate passwords per role (defaults if not in `.env`):

- **Stjóri:** `admin` (`STJORI_PASSWORD_HASH` / legacy `ADMIN_PASSWORD_HASH`)
- **Notandi:** `user` (`NOTANDI_PASSWORD_HASH`)

Pick role on login, then enter that role’s password. Per-user accounts → backlog.

## PWA (installable app) — test

- **On by default** via `PWA_ENABLED=1` (or unset). **Revert:** `PWA_ENABLED=0` in server `.env` + restart — see `docs/PWA.md`.
- Board banner **Setja upp** + browser install chip (Chrome/Edge).

## User research summary

- **Owner:** needs “neglect” visibility on the board, not only inside orders.  
- **Clerk:** needs fast phone lookup, pickup obvious, fewer scary mis-clicks.  
- See `docs/BACKLOG.md` for prioritized next work (Tier 2+).

## Planned (Tier 3)

- **SMS:** spare Android + Hringdu SIM, self-hosted gateway API — see `docs/BACKLOG.md` → SMS notifications.

## Source of truth

This GitHub repo: **https://github.com/Lovedealer8472/Muninn**

Server copies are deployed artifacts; edit here, then `deploy/deploy-th.ps1`.
