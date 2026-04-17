import os
import logging
from anticheat import create_verification_app

PORT = int(os.environ.get("PORT", 8000))
DB_PATH = os.environ.get("DB_PATH", "/data/bot_database.db")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "NeturalPredictorbot")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.info("🚀 Starting Bot Web Server...")
logging.info(f"📂 DB_PATH: {DB_PATH}")
logging.info(f"🤖 BOT_USERNAME: {BOT_USERNAME}")

app = create_verification_app(DB_PATH=DB_PATH, BOT_USERNAME=BOT_USERNAME)

@app.route("/")
def root():
    return {
        "status": "running",
        "mode": "telegram_only",
        "message": "Mine game web UI is disabled. Use the Telegram bot game only.",
        "bot_username": BOT_USERNAME,
        "routes": ["/ping", "/debug"]
    }

@app.route("/ping")
def ping():
    return "pong"

@app.route("/debug")
def debug_info():
    return {
        "status": "running",
        "mode": "telegram_only",
        "db_path": DB_PATH,
        "bot": BOT_USERNAME
    }

@app.errorhandler(404)
def not_found(e):
    return {
        "error": "Not Found",
        "message": "This Railway web service only handles bot health and verification routes. Mine web UI has been disabled.",
        "valid_routes": ["/", "/ping", "/debug"]
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
