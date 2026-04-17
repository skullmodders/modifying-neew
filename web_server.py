import os
import logging
import sqlite3
import json
from flask import render_template, redirect, request
from anticheat import create_verification_app

PORT = int(os.environ.get("PORT", 8000))
DB_PATH = os.environ.get("DB_PATH", "/data/bot_database.db")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "NeturalPredictorbot")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("🚀 Starting IP Verification Server...")
logging.info(f"📂 DB_PATH: {DB_PATH}")
logging.info(f"🤖 BOT_USERNAME: {BOT_USERNAME}")

app = create_verification_app(DB_PATH=DB_PATH, BOT_USERNAME=BOT_USERNAME)


def setting(key, default=None):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        conn.close()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]
    except Exception:
        return default


def mine_context():
    grid_size = max(3, min(10, int(setting("mine_grid_size", 5) or 5)))
    mines_min = max(1, int(setting("mine_min_mines", 1) or 1))
    mines_max = min(grid_size * grid_size - 1, int(setting("mine_max_mines", max(1, grid_size * grid_size - 1)) or max(1, grid_size * grid_size - 1)))
    route_path = str(setting("mine_web_path", "/mine") or "/mine").strip() or "/mine"
    if not route_path.startswith("/"):
        route_path = "/" + route_path
    return {
        "grid_size": grid_size,
        "tiles": grid_size * grid_size,
        "mines_min": mines_min,
        "mines_max": max(mines_min, mines_max),
        "min_bet": setting("mine_min_bet", 1),
        "max_bet": setting("mine_max_bet", 500),
        "base_multiplier": setting("mine_base_multiplier", 1.12),
        "progressive_rate": setting("mine_progressive_multiplier_rate", 0.24),
        "max_cap": setting("mine_max_multiplier_cap", 25),
        "jackpot": setting("mine_jackpot_multiplier", 50),
        "enabled": bool(setting("mine_game_enabled", True)),
        "telegram_enabled": bool(setting("mine_telegram_enabled", True)),
        "web_enabled": bool(setting("mine_web_enabled", True)),
        "sound_enabled": bool(setting("mine_sound_effects_enabled", True)),
        "risk_enabled": bool(setting("mine_risk_indicator_enabled", True)),
        "auto_cashout": bool(setting("mine_auto_cash_out_enabled", False)),
        "safe_first_tile": bool(setting("mine_force_safe_first_tile", True)),
        "route_path": route_path,
        "bot_username": BOT_USERNAME,
    }


@app.route("/")
def root():
    return redirect("/ping")


@app.route("/mine")
@app.route("/mine-game")
@app.route("/games/mine")
def mine_ui():
    ctx = mine_context()
    if not ctx["web_enabled"] or not ctx["enabled"]:
        return render_template("mine.html", **ctx)
    return render_template("mine.html", **ctx)


@app.route("/debug")
def debug_info():
    ctx = mine_context()
    return {
        "status": "running",
        "db_path": DB_PATH,
        "bot": BOT_USERNAME,
        "mine_route": ctx["route_path"],
        "mine_game_enabled": ctx["enabled"],
        "mine_web_enabled": ctx["web_enabled"],
        "mine_telegram_enabled": ctx["telegram_enabled"],
        "env_vars": list(os.environ.keys())
    }


@app.route("/ping")
def ping():
    return "pong"




@app.route("/<path:any_path>")
def dynamic_pages(any_path):
    ctx = mine_context()
    current = "/" + (any_path or "").strip("/")
    if current == ctx["route_path"]:
        return render_template("mine.html", **ctx)
    return not_found(None)


@app.errorhandler(404)
def not_found(e):
    return {
        "error": "Not Found",
        "message": "Invalid route",
        "valid_routes": ["/ping", "/debug", "/mine", "/mine-game", "/games/mine"]
    }, 404


@app.errorhandler(500)
def server_error(e):
    return {
        "error": "Server Error",
        "message": "Something went wrong"
    }, 500


if __name__ == "__main__":
    logging.info(f"🌐 Running on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)
