# Muninn PWA (installable app)

Experimental **Progressive Web App** support so staff can install Muninn from Chrome/Edge and get a **separate taskbar window** instead of another browser tab.

## Enable / disable (instant revert)

On the server (`/opt/pantanir-tolvuhvisl/.env`):

```bash
# On (default for this test)
PWA_ENABLED=1

# Off — removes manifest + service worker routes; pages behave as before
PWA_ENABLED=0
```

Then restart:

```bash
sudo systemctl restart pantanir-tolvuhvisl
```

No code deploy needed to turn it off.

## Fully remove after testing

1. Set `PWA_ENABLED=0` and restart (above).
2. On each PC: uninstall **Muninn** from Windows (Installed apps) or Chrome → ⋮ → *Uninstall Muninn*.
3. Optional: `git revert` the PWA commit in the Muninn repo and redeploy.

## How to install (clerks)

1. Open **https://th.tolvuhvislarinn.is** in **Chrome** or **Edge** (HTTPS required).
2. Log in as usual.
3. Either:
   - Click **Setja upp** on the yellow banner on the board, or
   - Use the browser install control (⊕ / “Install app” in the address bar).
4. Muninn opens in its own window; pin it to the taskbar.

**Safari / Firefox:** install UX differs; Chrome/Edge on the shop PC is the target.

## Files (for developers)

| File | Role |
|------|------|
| `app/static/sw.js` | Service worker (static cache only) |
| `app/static/pwa.js` | Register SW + install banner |
| `app/static/pwa-icon-*.png` | Manifest icons |
| `app/app.py` | `PWA_ENABLED`, `/manifest.webmanifest`, `/sw.js` |
| `scripts/generate_pwa_icons.py` | Regenerate icons from logo |

Bump `CACHE` in `sw.js` after changing cached static files.

## Bump cache version

Edit `CACHE` in `app/static/sw.js` (e.g. `muninn-static-v2`), deploy, hard-refresh installed app once.
