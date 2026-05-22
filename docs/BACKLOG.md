# Muninn backlog

Ordered by **impact × ease** (see conversation 2026-05-22).

## Done — Tier 1

- [x] Overdue ETA / Seinkað on board cards  
- [x] Days since update (`Nd`) on cards  
- [x] Contact status badge on cards  
- [x] Komið card highlight + “Til afhendingar”  
- [x] Search hint + phone-digit matching  
- [x] Status legend info modal (board header)  
- [x] Lokið = afhent hint on detail  
- [x] Status change redirect → order detail  

## Done — Tier 2 (Wave A)

- [x] Stale filter (`?stale=7`, oldest `updated_at` first in column)  
- [x] Email sent/failed/info banner on order after advance  
- [x] Comment count on board cards  

## Tier 2 — Next (Wave B)

- [ ] Counter / lookup mode (`/leita`)  
- [ ] Clerk-simplified detail (collapse Saga / Viðhengi)  
- [ ] Pickup-oriented print slip  

## Tier 3+

- Daily digest email  
- SMS  
- Attention dashboard strip  

## Later (auth)

- [ ] **Separate logins per person** (SQLite `users`, username + password + role) — shared shop password for now  
- [ ] Optional: force role from password (two env hashes) instead of radio at login  
