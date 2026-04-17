import os
import logging
import sqlite3
import json
from flask import render_template
from anticheat import create_verification_app

# ================== CONFIG ==================

PORT = int(os.environ.get("PORT", 8000))
DB_PATH = os.environ.get("DB_PATH", "/data/bot_database.db")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "NeturalPredictorbot")

# ================== LOGGING ==================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logging.info("🚀 Starting IP Verification Server...")
logging.info(f"📂 DB_PATH: {DB_PATH}")
logging.info(f"🤖 BOT_USERNAME: {BOT_USERNAME}")

# ================== CREATE APP ==================

app = create_verification_app(
    DB_PATH=DB_PATH,
    BOT_USERNAME=BOT_USERNAME
)

# ================== EXTRA ROUTES ==================



@app.route("/games/mine")
def mine_ui():
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

    grid_size = int(setting("mine_grid_size", 5) or 5)
    mines_min = int(setting("mine_min_mines", 1) or 1)
    mines_max = int(setting("mine_max_mines", max(1, grid_size * grid_size - 1)) or max(1, grid_size * grid_size - 1))
    return render_template(
        "mine.html",
        grid_size=grid_size,
        tiles=grid_size * grid_size,
        mines_min=mines_min,
        mines_max=mines_max,
        min_bet=setting("mine_min_bet", 1),
        max_bet=setting("mine_max_bet", 500),
        base_multiplier=setting("mine_base_multiplier", 1.12),
        progressive_rate=setting("mine_progressive_multiplier_rate", 0.24),
        max_cap=setting("mine_max_multiplier_cap", 25),
        jackpot=setting("mine_jackpot_multiplier", 50),
        enabled=bool(setting("mine_game_enabled", True)),
        sound_enabled=bool(setting("mine_sound_effects_enabled", True)),
        risk_enabled=bool(setting("mine_risk_indicator_enabled", True)),
        auto_cashout=bool(setting("mine_auto_cash_out_enabled", False)),
    )

@app.route("/debug")
def debug_info():
    return {
        "status": "running",
        "db_path": DB_PATH,
        "bot": BOT_USERNAME,
        "env_vars": list(os.environ.keys())
    }

@app.route("/ping")
def ping():
    return "pong"

# ================== ERROR HANDLING ==================

@app.errorhandler(404)
def not_found(e):
    return {
        "error": "Not Found",
        "message": "Invalid route"
    }, 404

@app.errorhandler(500)
def server_error(e):
    return {
        "error": "Server Error",
        "message": "Something went wrong"
    }, 500

# ================== START ==================

if __name__ == "__main__":
    logging.info(f"🌐 Running on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)
