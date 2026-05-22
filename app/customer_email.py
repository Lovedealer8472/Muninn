"""Customer notification email content (plain + HTML)."""
from __future__ import annotations

import html
import os
from typing import Any, Optional


def _shop_context() -> dict[str, str]:
    return {
        "name": os.environ.get("SHOP_NAME", "Tölvuhísill").strip(),
        "phone": os.environ.get("SHOP_PHONE", "").strip(),
        "url": os.environ.get("SHOP_URL", "https://tolvuhvislarinn.is").strip(),
    }


def _product_summary(order: dict[str, Any]) -> str:
    name = (order.get("product_name") or "").strip()
    model = (order.get("product_model") or "").strip()
    if name and model:
        return f"{name} ({model})"
    return name or "Vara"


def _order_ref(order: dict[str, Any]) -> str:
    return f"#{order['id']}"


def build_customer_notification(
    order: dict[str, Any], *, track_url: Optional[str] = None
) -> Optional[tuple[str, str, str, str]]:
    """Return (to_email, subject, text_body, html_body) or None."""
    status = order["status"]
    to_email = (order.get("email") or "").strip()
    if not to_email:
        return None

    shop = _shop_context()
    customer_raw = (order.get("customer_name") or "viðskiptavin").strip()
    customer = html.escape(customer_raw)
    product_raw = _product_summary(order)
    order_ref = _order_ref(order)
    eta = (order.get("estimated_arrival") or "").strip()

    if status == "Staðfest":
        subject = f"Pöntun {order_ref} staðfest — {shop['name']}"
        lead = (
            f"Pöntun {order_ref} ({product_raw}) hefur verið "
            f"staðfest hjá birgi og er á leiðinni til okkar."
        )
        if eta:
            detail = f"Áætluð koma: {eta}."
            closing = "Við látum þig vita þegar varan er tilbúin til afhendingar."
        else:
            detail = None
            closing = "Við látum þig vita þegar varan er komin."
    elif status == "Komið":
        subject = f"Tilbúin til afhendingar — {shop['name']}"
        lead = (
            f"{product_raw} (pöntun {order_ref}) "
            f"er komin og tilbúin til afhendingar hjá okkur."
        )
        detail = None
        closing = "Komdu við hæfis — við höfum samband ef þú hefur spurningar."
    else:
        if not track_url:
            return None
        subject = f"Uppfærsla á pöntun {order_ref} — {shop['name']}"
        lead = (
            f"Staða pöntunar {order_ref} ({product_raw}) "
            f"hefur verið uppfærð í: {status}."
        )
        detail = f"Fylgstu með: {track_url}"
        closing = None

    text = _plain_email(customer_raw, shop, lead, detail, closing)
    html_body = _html_email(customer, shop, lead, detail, closing, order_ref)
    return to_email, subject, text, html_body


def _plain_email(customer, shop, lead, detail, closing) -> str:
    lines = [f"Sæl(l) {customer},", "", lead]
    if detail:
        lines.extend(["", detail])
    if closing:
        lines.extend(["", closing])
    lines.extend(["", "Kveðja,", shop["name"]])
    if shop["phone"]:
        lines.append(f"Sími: {shop['phone']}")
    if shop["url"]:
        lines.append(shop["url"])
    return "\n".join(lines)


def _html_email(customer, shop, lead, detail, closing, order_ref) -> str:
    shop_name = html.escape(shop["name"])
    lead_html = html.escape(lead)
    detail_html = (
        f'<p style="margin:16px 0 0;font-size:15px;color:#374151;">{html.escape(detail)}</p>'
        if detail
        else ""
    )
    closing_html = (
        f'<p style="margin:16px 0 0;font-size:15px;color:#374151;">{html.escape(closing)}</p>'
        if closing
        else ""
    )
    footer_bits = [shop_name]
    if shop["phone"]:
        footer_bits.append(html.escape(shop["phone"]))
    if shop["url"]:
        url = html.escape(shop["url"])
        footer_bits.append(f'<a href="{url}" style="color:#6b7280;">{url}</a>')
    footer = " · ".join(footer_bits)

    return f"""<!DOCTYPE html>
<html lang="is">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{shop_name}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Segoe UI,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f4f6;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:520px;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08);">
          <tr>
            <td style="padding:20px 28px;background:#111827;color:#ffffff;font-size:18px;font-weight:600;">
              {shop_name}
            </td>
          </tr>
          <tr>
            <td style="padding:28px;">
              <p style="margin:0 0 8px;font-size:16px;color:#111827;">Sæl(l) {customer},</p>
              <p style="margin:0;font-size:15px;line-height:1.55;color:#374151;">{lead_html}</p>
              {detail_html}
              {closing_html}
              <p style="margin:28px 0 0;font-size:15px;color:#111827;">Kveðja,<br><strong>{shop_name}</strong></p>
            </td>
          </tr>
          <tr>
            <td style="padding:14px 28px;border-top:1px solid #e5e7eb;font-size:12px;line-height:1.5;color:#9ca3af;">
              {footer}<br>Pöntun {html.escape(order_ref)}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
