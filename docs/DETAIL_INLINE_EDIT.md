# Inline edit on order detail

Replaces the **Breyta** button with folded edit sections on the order detail page.

## On by default

`DETAIL_INLINE_EDIT=1` (or unset).

- **No Breyta** in the action bar
- **Quick fields:** Greiðsla, Samskipti, Forgangur
- **Folded sections:** Viðskiptavin, Vara og birgir, Dagsetningar, Innri athugasemd
- **Stjóri only:** link at bottom — *Full breyting (gamalt form)* — still opens the old full edit page (includes status dropdown)

## Rollback (restore Breyta button)

On the server (`/opt/pantanir-tolvuhvisl/.env`):

```env
DETAIL_INLINE_EDIT=0
```

Then restart:

```bash
sudo systemctl restart pantanir-tolvuhvisl
```

This restores the **Breyta** button and hides inline edit sections. The old `/order/<id>/edit` route is unchanged.

## Re-enable after rollback

Remove the line or set `DETAIL_INLINE_EDIT=1` and restart again.
