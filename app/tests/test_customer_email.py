"""Customer email copy (Icelandic)."""

from customer_email import build_customer_notification


def _order(**overrides):
    base = {
        "id": 42,
        "status": "Komið",
        "email": "k@example.is",
        "customer_name": "Jón",
        "product_name": "MacBook Pro",
        "product_model": "M3",
        "estimated_arrival": "",
    }
    base.update(overrides)
    return base


def test_komid_subject_and_body():
    _, subject, text, _ = build_customer_notification(_order())  # type: ignore[misc]
    assert "tilbúin" in subject.lower()
    assert "Sæl" not in text
    assert "Góðan dag Jón" in text
    assert "Komdu við hæfis" not in text
    assert "tilbúin til afhendingar" in text
    assert "opnunartíma" in text


def test_stadfest_with_eta():
    _, subject, text, _ = build_customer_notification(
        _order(status="Staðfest", estimated_arrival="15. júní")
    )  # type: ignore[misc]
    assert "staðfest" in subject.lower()
    assert "pönduð" in text
    assert "15. júní" in text
    assert "Gert er ráð fyrir" in text


def test_generic_uses_status_help():
    _, _, text, _ = build_customer_notification(
        _order(status="Í vinnslu"),
        track_url="https://pan.tolvuhvislarinn.is/fylgjast",
    )  # type: ignore[misc]
    assert "Verið er að vinna málið innanhúss" in text
    assert "fylgst með" in text


def test_no_email_returns_none():
    assert build_customer_notification(_order(email="")) is None
