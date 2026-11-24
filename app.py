"""Demo Monitoring Infrastructure — local Flask app (Step 1 shell)."""

from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def dashboard():
    """Empty dashboard shell — auth and metrics come in later steps."""
    return render_template("dashboard.html")


if __name__ == "__main__":
    # Local demo bind: all interfaces, port 5777 (see docs/requirements.md §8)
    app.run(host="0.0.0.0", port=5777, debug=True)
