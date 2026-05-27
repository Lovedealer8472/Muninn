# Muninn — evolution log

Chronicle of how Muninn grew from a shop-owner scratch pad into a deployable product.
Read newest sections first for current state; older sections show *why* decisions were made.

**Repo:** https://github.com/Lovedealer8472/Muninn  
**Author / operator:** Daði (Tölvuhvíslarinn ehf., Neskaupstaður)

---

## Timeline at a glance

| When | Milestone |
|------|-----------|
| Pre-repo | Pantanakerfi spreadsheet → monolithic Flask `app.py` on production server |
| 2026-05 (early) | Muninn branding; GitHub repo; `th.tolvuhvislarinn.is` dev instance |
| 2026-05-22 | Tier 1 + Tier 2 board UX; roles; PWA; email policy hardening |
| 2026-05-22+ | Drag-and-drop kanban; inline detail edit; engineering refactor |
| 2026-05-24 | 14-day trial SaaS shape: `pan.tolvuhvislarinn.is` |
| 2026-05-26 | Production data merge into pan; Icelandic email rewrite; market research |

---

## Phase 0 — The problem (pre-Git)

Tölvuhvíslarinn took **special orders** (computers, building materials, appliances) with **weeks of lead time**. State lived in:

- Minnisbækur  
- Email threads  
- Post-it miðar under the counter  

Failure mode: *“Er búið að panta fyrir Jón?”*, *“Er varan komin?”*, *“Hver átti að hringja?”*

**Design constraint from day one:** clerks need one shared truth, not another ERP.

---

## Phase 1 — Pantanakerfi monolith

Single `app.py` + SQLite (`pantanakerfi.db`) + vanilla templates.

Core ideas that survived every refactor:

1. **Kanban by Icelandic status** — not generic “Open/Closed”  
2. **Phone-based public tracking** — customers don’t need accounts  
3. **Order saga** — audit trail of field changes  
4. **Soft delete + Rusl** — 30-day retention before purge  

Pipeline settled as:

`Móttekið → Í vinnslu → Pantað → Staðfest → Komið → Lokið`

Production host: `pantanakerfi.tolvuhvislarinn.is` (`/opt/pantanakerfi`).

---

## Phase 2 — Muninn repo & TH instance (commit `2d5192a`)

**2026-05** — Extracted to GitHub as **Muninn**; primary dev on **`th.tolvuhvislarinn.is`**.

Shipped in early commits:

- Muninn branding (raven, quotes, optional PWA)  
- **Tier 1 board UX** — stale/idle badges, contact on cards, Komið highlight, search by phone digits, status legend modal  
- **Stjóri / Notandi** roles — separate passwords (`admin` / `user`)  
- **PWA** behind `PWA_ENABLED` kill switch  

Infrastructure split:

| Instance | Port | Purpose |
|----------|------|---------|
| pantanakerfi | 5000 | Original production branding |
| pantanir-tolvuhvisl (TH) | 5001 | Muninn development & dogfooding |
| pan-tolvuhvisl | 5003 | Trial / demo (later) |

---

## Phase 3 — Email becomes a product feature

Customer email was iterated hard because it’s the **“varan þín er tilbúin”** moment.

| Commit / change | Behaviour |
|-----------------|-----------|
| Auto email only on **Komið** | Not on Lokið or every status change |
| Trash restore | `suppress_auto_email` until manual Email |
| Background SMTP thread | UI doesn’t freeze; poll banner on detail |
| Saga `_email_notify` events | Clerk sees send result in history |
| HTML + plain templates | Migadu SMTP from `.env` |
| **2026-05-26 rewrite** | Natural Icelandic (`Góðan dag…`, not “Sæl(l)”; fixed “Komdu við hæfis”) |

Manual **Email** button always available for other statuses (uses `STATUS_HELP` text in generic template).

---

## Phase 4 — Clerk & owner feedback (Tier 2)

From real use at Tölvuhvíslarinn:

**Owner wants:** neglect visible on the **board** (not buried in orders).  
**Clerk wants:** fast phone lookup, obvious pickup, fewer mis-clicks.

Delivered:

- **Tier 2 Wave A** — stale filter, comment badges, email result banner  
- **Drag-and-drop** (SortableJS) — Notandi: next column only; Stjóri: any column  
- **Geyma** — archive when Lokið + Greitt  
- **Inline detail edit** (`DETAIL_INLINE_EDIT=1`) — Greiðsla / Samskipti / Forgangur on detail; optional rollback to old form  
- Reworked create form — fewer required fields, folded dates  

---

## Phase 5 — Engineering hardening (package refactor)

Monolithic `app.py` (~1600 lines) → **`app/muninn/`** package:

```
app/
  app.py                 # create_app() entry only
  customer_email.py      # Icelandic notification copy
  muninn/
    config.py, db.py, auth.py, trial.py
    services/ email.py, orders.py
    routes/ board, orders, public, api, …
  tests/                 # pytest
```

Also added:

- `LOG_LEVEL` structured logging  
- `.env.example`  
- `scripts/backup_db.sh`  
- `docs/ENGINEERING.md`  
- Deploy smoke check in `deploy-th.ps1`  
- **19+ pytest tests** (orders logic, trial, customer email, …)

Goal: v1 maintainability without changing clerk-visible behaviour.

---

## Phase 6 — Trial instance & product shape

**2026-05-24** — `pan.tolvuhvislarinn.is`:

- `TRIAL_EXPIRES_AT` env — banner with days left; 403 page after expiry  
- `deploy/deploy-pan.ps1` + `pan-trial-setup.sh` (nginx, certbot, systemd)  
- SMTP copied from TH on first setup  
- **14-day free trial** for prospects  

**2026-05-26** — Merged live data from `pantanakerfi.tolvuhvislarinn.is` into pan (`scripts/merge_pantanakerfi_to_pan.py`) for realistic demos.

Docs: `docs/PAN_TRIAL.md`, `docs/MARKET_RESEARCH.md`.

---

## Phase 7 — What Muninn is *not* (on purpose)

Documented so future-you doesn’t scope-creep:

- Not POS (Exigo/Odoo territory)  
- Not ERP (Uniconta/Stólpi territory)  
- Not full repair-shop SaaS (RepairShopr/RepairOps — English, USD, ticket-centric)  

**Wedge:** Icelandic **supplier-wait → pickup** kanban for 1–8 staff shops.

---

## Deploy map (current)

| URL | Service | Notes |
|-----|---------|-------|
| https://th.tolvuhvislarinn.is | `pantanir-tolvuhvisl` | Dev / dogfood; no trial expiry |
| https://pan.tolvuhvislarinn.is | `pan-tolvuhvisl` | 14-day trial; demo data |
| https://pantanakerfi.tolvuhvislarinn.is | `pantanakerfi` | Production Pantanakerfi — deploy only when asked |

Deploy from Windows:

```powershell
.\deploy\deploy-th.ps1   # TH
.\deploy\deploy-pan.ps1  # trial instance
```

---

## Feature flags & rollback levers

| Env var | Effect |
|---------|--------|
| `PWA_ENABLED=0` | Disable installable PWA |
| `DETAIL_INLINE_EDIT=0` | Restore separate Breyta form |
| `TRIAL_EXPIRES_AT` | Set on trial instances only; omit on TH/prod |
| `LOG_LEVEL=DEBUG` | Verbose request logging |

---

## Planned next (see BACKLOG.md)

- `/leita` dedicated search  
- Clerk-simplified detail  
- Pickup print slip  
- SMS via self-hosted Android gateway (Hringdu SIM)  
- Per-user accounts (today: shared role passwords)

---

## How to read Git history

```bash
git log --oneline --reverse   # oldest → newest
git log --oneline -20         # recent work
```

Major tags in commit messages: `Tier 1`, `Tier 2`, `PWA`, `email`, `roles`.

---

*Update this file when a phase completes — not every commit, but every **product** milestone.*
