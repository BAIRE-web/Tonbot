import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# Récupération sécurisée du token
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# === Réponse à la commande /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Ton bot Telegram fonctionne parfaitement avec Render et Docker !")

# === Petit serveur HTTP pour éviter l'arrêt du service sur Render ===
def lancer_http():
    port = int(os.environ.get("PORT", 10000))  # Port fourni par Render
    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot actif ✅")
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# === Lancement du bot ===
def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

# === Lancer le bot et le serveur HTTP en parallèle ===
if __name__ == "__main__":
    threading.Thread(target=lancer_http).start()
    lancer_bot()
