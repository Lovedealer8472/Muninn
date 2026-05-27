"""Register all HTTP routes on the Flask app."""

from flask import Flask

from muninn.routes import attachments, auth, board, orders, public, pwa, api


def register_routes(app: Flask) -> None:
    for register in (
        pwa.register,
        auth.register,
        public.register,
        board.register,
        api.register,
        orders.register,
        attachments.register,
    ):
        register(app)
