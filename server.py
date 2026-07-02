"""
Commercial Override — Flask web server

Detects commercial breaks in a (simulated) live TV broadcast and switches
the screen to the business's own promo spots, then switches back when
programming resumes.

Run locally:  python server.py  → opens http://localhost:5050/co/
Deployed:     gunicorn server:app  (PORT env var is respected)
"""
import os
import webbrowser

from flask import Flask, redirect

from commercial_override import co_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "commercial-override-secret")
app.register_blueprint(co_bp)


@app.route("/")
def home():
    return redirect("/co/")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("=" * 50)
    print("  AD-SHARK — Commercial Killer")
    print(f"  TV:        http://localhost:{port}/co/")
    print(f"  Dashboard: http://localhost:{port}/co/dashboard")
    print("=" * 50)
    if port == 5050:
        webbrowser.open(f"http://localhost:{port}/co/")
    app.run(debug=False, host="0.0.0.0", port=port)
