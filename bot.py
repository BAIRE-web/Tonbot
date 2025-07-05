import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# 👉 Ton token est à stocker dans les variables d'environnement (plus sécurisé)
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Ajoute ça dans Render > Environment

# === Commande /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌟 Salut ! Ton bot est connecté et prêt à te répondre sur Render 🚀")

# === Serveur HTTP pour Render (port obligatoire) ===
def lancer_http():
    port = int(os.environ.get("PORT", 10000))  # Utilise le port attribué par Render

    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot Telegram actif.")

    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# === Lancement du bot Telegram ===
def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

# === Lancement des deux services ===
if __name__ == "__main__":
    threading.Thread(target=lancer_http).start()
    lancer_bot()
