# Muninn — project status

*Last updated: 2026-05-22*

## Product

Muninn is a lightweight **special-order / repair tracking** tool: kanban board, order detail, customer email on status changes, public tracking by phone, attachments, comments, soft-delete trash (30 days).

**Primary deploy target:** `th.tolvuhvislarinn.is` (`/opt/pantanir-tolvuhvisl` on edge `100.79.10.104`).

**Not in scope unless asked:** `pantanakerfi.tolvuhvislarinn.is` (production Pantanakerfi branding).

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
| **Stjóri / Notandi roles** (2026-05-22) | Live on TH — shared password, role at login |

### Tier 1 (clerk / owner feedback)

1. Overdue + idle-day badges on board cards  
2. Contact status on cards  
3. Komið highlighted (“Til afhendingar”)  
4. Search placeholder + phone-digit search  
5. Collapsible status legend on board  
6. Lokið clarified as “(afhent)” on detail pipeline  
7. After status change from board dropdown → return to **order detail** (modal path already on detail)

## Infrastructure

- **Service:** `pantanir-tolvuhvisl.service` (port 5001)  
- **DB:** `app/pantanakerfi.db` (SQLite, WAL)  
- **SMTP:** Migadu via `.env` on server  

## Roles (Stjóri / Notandi)

| | **Notandi** | **Stjóri** |
|---|-------------|------------|
| Board, search, new order | Yes | Yes |
| Færa áfram (+ email modal) | Yes (next step only) | Yes |
| Breyta, Ummæli, QR, Prenta | Yes | Yes |
| Status dropdown on cards | No | Yes |
| Eyða / Rusl | No | Yes |
| Tölfræði | No | Yes |

One shop password for both; pick role on login. Per-user accounts → backlog.

## User research summary

- **Owner:** needs “neglect” visibility on the board, not only inside orders.  
- **Clerk:** needs fast phone lookup, pickup obvious, fewer scary mis-clicks.  
- See `docs/BACKLOG.md` for prioritized next work (Tier 2+).

## Source of truth

This GitHub repo: **https://github.com/Lovedealer8472/Muninn**

Server copies are deployed artifacts; edit here, then `deploy/deploy-th.ps1`.
