"""Demo Monitoring Infrastructure — local Flask app."""

from __future__ import annotations

from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

import config
import metrics
import store

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_globals():
    return {
        "refresh_seconds": config.METRICS_REFRESH_SECONDS,
        "username": session.get("username"),
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == config.ADMIN_USERNAME and check_password_hash(
            config.ADMIN_PASSWORD_HASH, password
        ):
            session["authenticated"] = True
            session["username"] = username
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    servers = store.list_servers()
    rows = metrics.collect_summaries(servers)
    return render_template("dashboard.html", servers=rows)


@app.route("/servers/add", methods=["GET", "POST"])
@login_required
def add_server():
    if request.method == "POST":
        name = request.form.get("name") or ""
        host = request.form.get("host") or ""
        port_raw = request.form.get("port") or "22"
        ssh_user = request.form.get("ssh_user") or ""
        ssh_password = request.form.get("ssh_password") or ""

        if not all([name.strip(), host.strip(), ssh_user.strip(), ssh_password]):
            flash("All fields are required.", "error")
            return render_template("add_server.html", form=request.form)

        try:
            port = int(port_raw)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            flash("SSH port must be a number between 1 and 65535.", "error")
            return render_template("add_server.html", form=request.form)

        store.add_server(name, host, port, ssh_user, ssh_password)
        flash(f"Server “{name.strip()}” added.", "ok")
        return redirect(url_for("dashboard"))

    return render_template("add_server.html", form={})


@app.route("/servers/<server_id>")
@login_required
def server_detail(server_id: str):
    server = store.get_server(server_id)
    if not server:
        flash("Server not found.", "error")
        return redirect(url_for("dashboard"))

    live = metrics.collect_metrics(server)
    safe = {k: v for k, v in server.items() if k != "ssh_password"}
    return render_template("server_detail.html", server=safe, metrics=live)


@app.route("/servers/<server_id>/remove", methods=["POST"])
@login_required
def remove_server(server_id: str):
    server = store.get_server(server_id)
    if store.remove_server(server_id):
        label = server["name"] if server else server_id
        flash(f"Server “{label}” removed.", "ok")
    else:
        flash("Server not found.", "error")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=57275, debug=True)
