"""Flask app: the /TTRPG front door and one blueprint per game."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from ttrpgtools.dh1e.storage import CHARACTERS_DIR

# the slim container image does not know these; a texture or font sent as octet-stream may be refused
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("font/otf", ".otf")
mimetypes.add_type("font/woff2", ".woff2")


def create_app() -> Flask:
    # static_url_path is namespaced under /TTRPG because Caddy routes the whole
    # /sheet* prefix (path intact, not stripped) to this container -- url_for()
    # must generate links that match what Caddy will actually forward.
    app = Flask(__name__, static_url_path="/TTRPG/static")
    CHARACTERS_DIR.mkdir(exist_ok=True)

    @app.template_global()
    def static_v(filename: str) -> str:
        """A static URL with ?v=<mtime>: Cloudflare caches static files, and an unversioned URL kept
        serving the old dnd5e.css after a deploy (2026-10-22, the Characters banner showed unstyled)."""
        path = Path(app.static_folder) / filename
        version = int(path.stat().st_mtime) if path.exists() else 0
        return url_for("static", filename=filename) + f"?v={version}"
    from ttrpgtools.permissions import may_delete
    app.add_template_global(may_delete)
    from ttrpgtools.dcc.routes import bp as dcc_bp
    from ttrpgtools.dh1e.routes import bp as dh1e_bp
    from ttrpgtools.dnd5e.builder_routes import bp as dnd5e_builder_bp
    from ttrpgtools.dnd5e.routes import bp as dnd5e_bp
    for bp in (dcc_bp, dh1e_bp, dnd5e_bp, dnd5e_builder_bp):
        app.register_blueprint(bp)

    @app.get("/")
    def index():
        return redirect(url_for("hub"))

    @app.get("/TTRPG", strict_slashes=False)
    def hub():
        """The front door: one tile per game. Everything of a game lives under /TTRPG/<game>/."""
        return render_template("hub.html")

    @app.route("/sheet", defaults={"rest": ""}, methods=["GET", "POST"])
    @app.route("/sheet/<path:rest>", methods=["GET", "POST"])
    def old_address(rest):
        """Everything used to live under /sheet. Old links and open tabs are sent on; 307 keeps a POST a POST."""
        first = rest.split("/", 1)[0]
        target = "/TTRPG" + ("/" + rest if first in ("dcc", "dnd5e", "static") else "/dh1e" + ("/" + rest if rest else ""))
        query = request.query_string.decode()
        return redirect(target + ("?" + query if query else ""), code=307)

    @app.route("/ttrpg", defaults={"rest": ""}, methods=["GET", "POST"])
    @app.route("/ttrpg/<path:rest>", methods=["GET", "POST"])
    def lower_case(rest):
        query = request.query_string.decode()
        return redirect("/TTRPG" + ("/" + rest if rest else "") + ("?" + query if query else ""), code=307)

    return app
