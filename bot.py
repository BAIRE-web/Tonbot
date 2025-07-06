import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# Récupération sécurisée du token
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# === Création du serveur Flask ===
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot actif ✅"

# === Lancement du serveur Flask dans un thread ===
def lancer_flask():
    port = int(os.environ.get("PORT", 10000))  # Port fourni par Render
    app.run(host="0.0.0.0", port=port)

# === Réponse à la commande /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Ton bot Telegram fonctionne parfaitement avec Render et Docker !")

# === Lancement du bot ===
def lancer_bot():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.run_polling()

# === Lancer Flask + bot en parallèle ===
if __name__ == "__main__":
    threading.Thread(target=lancer_flask).start()
    lancer_bot()
