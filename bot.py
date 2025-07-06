import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Récupère le token depuis Render

# === Commande /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Salut, ton bot est maintenant prêt sur Render avec succès !")

# === Serveur HTTP obligatoire pour Render ===
def lancer_http():
    port = int(os.environ.get("PORT", 10000))

    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Le bot Telegram est actif sur Render.")

    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# === Lancement du bot Telegram sans Updater ===
def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

# === Démarrage des deux processus ===
if __name__ == "__main__":
    threading.Thread(target=lancer_http).start()
    lancer_bot()
