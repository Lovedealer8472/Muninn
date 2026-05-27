from muninn import create_app

app = create_app()

if __name__ == "__main__":
    import os

    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"

    if debug:
        app.run(host=host, port=port, debug=True)
    else:
        from waitress import serve

        print(f"Pantanakerfi running on http://{host}:{port}")
        serve(app, host=host, port=port, threads=4)
