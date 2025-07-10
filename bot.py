import os import json import unicodedata import random import re import threading from datetime import datetime from flask import Flask from telegram import Update, ReplyKeyboardMarkup from telegram.ext import ( ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ) from telegram.error import Forbidden

DATA_DIR = "data" user_states = {} user_progress = {} user_states_avis = set() ADMIN_USER_ID = 6227031560 BOT_TOKEN = os.environ.get("BOT_TOKEN")

flask_app = Flask(name)

@flask_app.route("/") def home(): return "✅ Bot éducatif en ligne (Render + Flask + Telegram Bot)"

def lancer_flask(): port = int(os.environ.get("PORT", 10000)) flask_app.run(host="0.0.0.0", port=port)

def enlever_emojis(text): emoji_pattern = re.compile("[" u"\U0001F600-\U0001F64F" u"\U0001F300-\U0001F5FF" u"\U0001F680-\U0001F6FF" u"\U0001F1E0-\U0001F1FF" u"\U00002500-\U00002BEF" u"\U00002702-\U000027B0" u"\U000024C2-\U0001F251" u"\U0001f926-\U0001f937" u"\U00010000-\U0010ffff" u"\u2640-\u2642" u"\u2600-\u2B55" u"\u200d" u"\u23cf" u"\u23e9" u"\u231a" u"\ufe0f" u"\u3030" "]+", flags=re.UNICODE) return emoji_pattern.sub(r'', text).strip()

def log_message(user_id, message): chemin = os.path.join("logs", f"{user_id}.txt") now = datetime.now().strftime("%Y-%m-%d %H:%M:%S") with open(chemin, "a", encoding="utf-8") as f: f.write(f"[{now}] {message}\n")

def increment_stat(cle): chemin = "stats.json" stats = {} if os.path.exists(chemin): with open(chemin, "r", encoding="utf-8") as f: stats = json.load(f) stats[cle] = stats.get(cle, 0) + 1 with open(chemin, "w", encoding="utf-8") as f: json.dump(stats, f, ensure_ascii=False, indent=2)

def normaliser_nom(nom): nom = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode("utf-8") return nom.lower().replace(" ", "_")

def charger_json(fichier): chemin = os.path.join(DATA_DIR, fichier) if os.path.exists(chemin): with open(chemin, "r", encoding="utf-8") as f: return json.load(f) return {}

def sauvegarder_utilisateur(user): chemin = os.path.join(DATA_DIR, "users.json") users = {} if os.path.exists(chemin): with open(chemin, "r", encoding="utf-8") as f: users = json.load(f) uid = str(user.id) if uid not in users: users[uid] = {"username": user.username or "", "nom": user.full_name or "", "bienvenue": False} else: users[uid]["username"] = user.username or users[uid].get("username", "") users[uid]["nom"] = user.full_name or users[uid].get("nom", "") with open(chemin, "w", encoding="utf-8") as f: json.dump(users, f, ensure_ascii=False, indent=2)

def generer_clavier(options): return ReplyKeyboardMarkup([[opt] for opt in options], resize_keyboard=True)

async def repondre(update: Update, message: str, clavier=None): log_message(update.effective_user.id, f"Bot: {message}") await update.message.reply_text(message, reply_markup=clavier)

messages = charger_json("messages.json") intros = charger_json("intro.json") claviers = charger_json("claviers.json")

# --- Nouvelle commande /listeavis réservée à l'admin pour voir les avis ---
async def listeavis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await repondre(update, "❌ Vous n'êtes pas autorisé à utiliser cette commande.")
        return

    chemin_avis = "avis.json"
    if not os.path.exists(chemin_avis):
        await repondre(update, "Aucun avis n'a encore été envoyé.")
        return

    try:
        with open(chemin_avis, "r", encoding="utf-8") as f:
            avis_list = json.load(f)
    except Exception as e:
        await repondre(update, f"Erreur lors de la lecture des avis : {e}")
        return

    if not avis_list:
        await repondre(update, "Aucun avis enregistré.")
        return

    # Construire un message avec les avis (limiter la taille pour Telegram)
    messages_avis = []
    for avis in avis_list:
        msg = f"👤 @{avis.get('username','inconnu')} (ID: {avis.get('user_id')})\n" \
              f"🕒 {avis.get('date')}\n" \
              f"💬 {avis.get('message')}\n\n"
        messages_avis.append(msg)

    # Telegram limite les messages à 4096 caractères, on découpe si nécessaire
    chunk_size = 3500
    chunks = []
    current_chunk = ""
    for m in messages_avis:
        if len(current_chunk) + len(m) > chunk_size:
            chunks.append(current_chunk)
            current_chunk = m
        else:
            current_chunk += m
    if current_chunk:
        chunks.append(current_chunk)

    for chunk in chunks:
        await update.message.reply_text(chunk)

# Ajout de la commande dans le bot
def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("avis", avis_command))  # Commande pour envoyer un avis
    app.add_handler(CommandHandler("listeavis", listeavis))  # Commande admin pour voir les avis
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()

if __name__ == "__main__":
    if not os.path.exists("logs"):
        os.makedirs("logs")
    threading.Thread(target=lancer_flask).start()
    lancer_bot()
