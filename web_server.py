
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


def normalize_path(path_value, fallback="/mine"):
    path_value = str(path_value or fallback).strip() or fallback
    if not path_value.startswith("/"):
        path_value = "/" + path_value
    path_value = "/" + path_value.strip("/")
    return path_value or fallback


def normalized_aliases():
    aliases = {
        "/mine",
        "/mine-game",
        "/games/mine",
        normalize_path(setting("mine_web_path", "/mine"), "/mine"),
    }
    return aliases


def mine_context():
    grid_size = max(3, min(10, int(setting("mine_grid_size", 5) or 5)))
    mines_min = max(1, int(setting("mine_min_mines", 1) or 1))
    mines_max = min(grid_size * grid_size - 1, int(setting("mine_max_mines", max(1, grid_size * grid_size - 1)) or max(1, grid_size * grid_size - 1)))
    route_path = normalize_path(setting("mine_web_path", "/mine"), "/mine")
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
        "games_enabled": bool(setting("games_section_enabled", True)),
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


def should_serve_mine(path_value):
    normalized = normalize_path(path_value, "/mine")
    return normalized in normalized_aliases()


def render_mine_page():
    ctx = mine_context()
    return render_template("mine.html", **ctx)


@app.route("/")
def root():
    if should_serve_mine("/mine"):
        return redirect("/mine")
    return redirect("/ping")


@app.route("/mine", strict_slashes=False)
@app.route("/mine-game", strict_slashes=False)
@app.route("/games/mine", strict_slashes=False)
def mine_ui_aliases():
    return render_mine_page()


@app.route("/debug")
def debug_info():
    ctx = mine_context()
    return {
        "status": "running",
        "db_path": DB_PATH,
        "bot": BOT_USERNAME,
        "mine_route": ctx["route_path"],
        "mine_aliases": sorted(list(normalized_aliases())),
        "games_enabled": ctx["games_enabled"],
        "mine_game_enabled": ctx["enabled"],
        "mine_web_enabled": ctx["web_enabled"],
        "mine_telegram_enabled": ctx["telegram_enabled"],
        "request_path": request.path,
    }


@app.route("/ping")
def ping():
    return "pong"


@app.route("/<path:any_path>", strict_slashes=False)
def dynamic_pages(any_path):
    requested = normalize_path(any_path)
    if should_serve_mine(requested):
        return render_mine_page()
    return not_found(None)


@app.errorhandler(404)
def not_found(e):
    return {
        "error": "Not Found",
        "message": "Invalid route",
        "valid_routes": sorted(list(normalized_aliases())) + ["/ping", "/debug"],
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
