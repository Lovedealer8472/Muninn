"""Application constants and configuration values."""

import os

from werkzeug.security import generate_password_hash

_STJORI_DEFAULT_HASH = generate_password_hash("admin")
_NOTANDI_DEFAULT_HASH = generate_password_hash("user")

STATUSES = [
    "Móttekið",
    "Í vinnslu",
    "Pantað",
    "Staðfest",
    "Komið",
    "Lokið",
]

PAYMENT_OPTIONS = ["Ógreitt", "Innborgun", "Greitt"]
CONTACT_OPTIONS = [
    "Ekki haft samband",
    "Haft samband",
    "Minnt á",
    "Næst ekki í viðskiptavin",
]
PRIORITY_OPTIONS = ["Venjulegt", "Mikilvægt", "Brýnt"]
TRASH_RETENTION_DAYS = 30

ROLE_STJORI = "stjori"
ROLE_NOTANDI = "notandi"
ROLE_LABELS = {
    ROLE_STJORI: "Stjóri",
    ROLE_NOTANDI: "Notandi",
}

AUTO_EMAIL_STATUS = "Komið"

STATUS_HELP = {
    "Móttekið": "Ný beiðni móttekin.",
    "Í vinnslu": "Verið er að vinna málið innanhúss.",
    "Pantað": "Pöntun send til birgja.",
    "Staðfest": "Birgir staðfestir; áætluð koma gildir.",
    "Komið": "Vara komin — tilbúin til afhendingar.",
    "Lokið": "Lokið / afhent viðskiptavini.",
}

CONTACT_SHORT = {
    "Ekki haft samband": "Ekki samb.",
    "Haft samband": "Samb.",
    "Minnt á": "Minnt á",
    "Næst ekki í viðskiptavin": "Næst ekki",
}

EVENT_FIELD_LABELS = {
    "status": "Staða",
    "payment_status": "Greiðslustaða",
    "contact_status": "Samskiptastaða",
    "priority": "Forgangur",
    "estimated_arrival": "Áætluð koma",
    "customer_name": "Nafn",
    "phone": "Sími",
    "email": "Netfang",
    "product_name": "Vara",
    "product_model": "Módel",
    "supplier": "Birgir",
    "notes": "Athugasemd",
    "date_ordered": "Pöntun send",
    "date_arrived": "Vara komin",
    "date_completed": "Lokið",
    "_created": "Stofnað",
    "_comment": "Ummæli",
    "_email_notify": "Tilkynning",
    "_archived": "Geymt",
    "_deleted": "Eytt",
    "_restored": "Endurheimt",
}

EMAIL_SAGA_SKIP = frozenset({"pending", "skipped"})

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per file
ALLOWED_EXT = {
    "pdf",
    "jpg", "jpeg", "png", "heic", "webp", "gif",
    "docx", "xlsx", "pptx", "doc", "xls", "ppt",
    "txt", "csv",
}

INLINE_EDIT_SECTIONS = {
    "customer": ("customer_name", "phone", "email"),
    "product": ("product_name", "product_model", "supplier"),
    "dates": (
        "date_requested",
        "date_ordered",
        "estimated_arrival",
        "date_arrived",
        "date_completed",
    ),
    "notes": ("notes",),
}

EMAIL_NOTICE = {
    "sent": ("Tilkynning send í tölvupósti til viðskiptavinar.", "success"),
    "failed": ("Póstur mistókst — reyndu aftur eða hringdu í viðskiptavin.", "error"),
    "no_email": ("Enginn póstur sendur (ekki netfang skráð).", "info"),
    "no_smtp": ("Póstur ekki sendur (SMTP ekki stillt á netþjóni).", "warning"),
    "skipped": ("Engin tilkynning fyrir þessa stöðu.", "info"),
    "pending": ("Tilkynning sendist…", "pending"),
}


def password_default_hashes():
    return _STJORI_DEFAULT_HASH, _NOTANDI_DEFAULT_HASH


def upload_root_for(app) -> str:
    return os.path.join(app.root_path, "uploads")
