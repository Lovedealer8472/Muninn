"""PWA manifest and service worker routes."""

import os

from flask import Flask, abort, current_app, jsonify, request, send_from_directory, url_for

from muninn.auth import pwa_enabled


def external_https(endpoint: str, **values):
    """Manifest/install needs https:// on production hosts behind nginx."""
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    if scheme != "https" and request.host.endswith(".tolvuhvislarinn.is"):
        scheme = "https"
    return url_for(endpoint, _external=True, _scheme=scheme, **values)


def register(app: Flask) -> None:
    @app.route("/manifest.webmanifest")
    def pwa_manifest():
        if not pwa_enabled():
            abort(404)
        icons = [
            {
                "src": external_https("static", filename="pwa-icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": external_https("static", filename="pwa-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": external_https("static", filename="pwa-icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ]
        return (
            jsonify(
                {
                    "name": "Muninn – Pantanir",
                    "short_name": "Muninn",
                    "description": "Pöntunakerfi Tölvuhíslarans",
                    "lang": "is",
                    "id": "/?pwa=muninn",
                    "start_url": external_https("board"),
                    "scope": "/",
                    "display": "standalone",
                    "orientation": "any",
                    "background_color": "#000000",
                    "theme_color": "#000000",
                    "icons": icons,
                }
            ),
            200,
            {"Content-Type": "application/manifest+json"},
        )

    @app.route("/sw.js")
    def pwa_service_worker():
        if not pwa_enabled():
            abort(404)
        response = send_from_directory(
            os.path.join(current_app.root_path, "static"),
            "sw.js",
            mimetype="application/javascript",
        )
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response
