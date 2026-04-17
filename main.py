from core import bot, ADMIN_ID, FORCE_JOIN_CHANNELS, NOTIFICATION_CHANNEL
import handlers  # noqa: F401 - registers all bot handlers on import
import time

print("=" * 50)
print("  UPI Loot Pay Bot Starting...")
print(f"  Admin ID: {ADMIN_ID}")
print(f"  Force Join: {FORCE_JOIN_CHANNELS}")
print(f"  Notification Channel: {NOTIFICATION_CHANNEL}")
print("=" * 50)

while True:
    try:
        print("Bot is polling...")
        bot.infinity_polling(
            timeout=60,
            long_polling_timeout=60,
            allowed_updates=["message", "callback_query"]
        )
    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(5)
