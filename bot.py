import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Récupération du token depuis les variables d’environnement
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Commande /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Bonjour, le bot fonctionne bien sur Render !")

# Lancement du bot
def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

# Faux serveur HTTP pour Render (port obligatoire)
def lancer_http():
    port = int(os.environ.get("PORT", 10000))
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot Telegram actif sur Render.")
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

# Lancement parallèle
if __name__ == "__main__":
    threading.Thread(target=lancer_bot).start()
    lancer_http()
