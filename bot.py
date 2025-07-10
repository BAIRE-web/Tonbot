import os
import json
import unicodedata
import random
import re
import threading
from datetime import datetime
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import Forbidden

DATA_DIR = "data"
user_states = {}
user_progress = {}
user_states_avis = set()  # Pour suivre les utilisateurs en mode "avis"
ADMIN_USER_ID = 6227031560
BOT_TOKEN = os.environ.get("BOT_TOKEN")

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Bot éducatif en ligne (Render + Flask + Telegram Bot)"

def lancer_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

def enlever_emojis(text):
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002500-\U00002BEF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u200d"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\ufe0f"
        u"\u3030"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text).strip()

def log_message(user_id, message):
    chemin = os.path.join("logs", f"{user_id}.txt")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {message}\n")

def increment_stat(cle):
    chemin = "stats.json"
    stats = {}
    if os.path.exists(chemin):
        with open(chemin, "r", encoding="utf-8") as f:
            stats = json.load(f)
    stats[cle] = stats.get(cle, 0) + 1
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def normaliser_nom(nom):
    nom = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode("utf-8")
    return nom.lower().replace(" ", "_")

def charger_json(fichier):
    chemin = os.path.join(DATA_DIR, fichier)
    if os.path.exists(chemin):
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def sauvegarder_utilisateur(user):
    chemin = os.path.join(DATA_DIR, "users.json")
    users = {}
    if os.path.exists(chemin):
        with open(chemin, "r", encoding="utf-8") as f:
            users = json.load(f)
    uid = str(user.id)
    if uid not in users:
        users[uid] = {"username": user.username or "", "nom": user.full_name or "", "bienvenue": False}
    else:
        users[uid]["username"] = user.username or users[uid].get("username", "")
        users[uid]["nom"] = user.full_name or users[uid].get("nom", "")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def generer_clavier(options):
    return ReplyKeyboardMarkup([[opt] for opt in options], resize_keyboard=True)

async def repondre(update: Update, message: str, clavier=None):
    log_message(update.effective_user.id, f"Bot: {message}")
    await update.message.reply_text(message, reply_markup=clavier)

messages = charger_json("messages.json")
intros = charger_json("intro.json")
claviers = charger_json("claviers.json")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, message_personnalise=True):
    user = update.effective_user
    user_id = str(user.id)
    sauvegarder_utilisateur(user)
    chemin = os.path.join(DATA_DIR, "users.json")
    with open(chemin, "r", encoding="utf-8") as f:
        users = json.load(f)
    deja_accueilli = users[user_id].get("bienvenue", False)
    nom = user.first_name or user.full_name or "cher utilisateur"

    if not deja_accueilli:
        msg = messages["bienvenue"].replace("{nom}", nom)
        users[user_id]["bienvenue"] = True
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    else:
        msg = messages["retour"] if message_personnalise else messages["choix"]

    user_states[user.id] = "menu"
    user_progress.pop(user.id, None)
    log_message(user.id, "Commande /start")
    await repondre(update, msg, generer_clavier(claviers["menu_principal"]))


# --- Commande /avis pour que l'utilisateur envoie un avis ---
async def avis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states_avis.add(user_id)
    await update.message.reply_text("Quel est votre avis ou suggestion ?")

async def avis_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states_avis:
        return False  # Pas en mode avis, on continue normalement

    texte = update.message.text.strip()
    chemin_avis = "avis.json"

    avis_list = []
    if os.path.exists(chemin_avis):
        with open(chemin_avis, "r", encoding="utf-8") as f:
            try:
                avis_list = json.load(f)
            except:
                avis_list = []

    avis_list.append({
        "user_id": user_id,
        "username": update.effective_user.username or "",
        "message": texte,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    with open(chemin_avis, "w", encoding="utf-8") as f:
        json.dump(avis_list, f, ensure_ascii=False, indent=2)

    user_states_avis.remove(user_id)
    await update.message.reply_text("Merci pour votre message !")
    await start(update, context)
    return True

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await repondre(update, messages["non_admin"])
        return
    msg = " ".join(context.args)
    if not msg:
        await repondre(update, "Utilise : /broadcast <message>")
        return
    chemin = os.path.join(DATA_DIR, "users.json")
    if not os.path.exists(chemin):
        await repondre(update, "Aucun utilisateur.")
        return
    with open(chemin, "r", encoding="utf-8") as f:
        users = json.load(f)
    count = 0
    for uid in users:
        try:
            await context.bot.send_message(chat_id=int(uid), text=msg)
            count += 1
        except Forbidden:
            pass
    await repondre(update, f"Message envoyé à {count} utilisateur(s).")

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await repondre(update, messages["non_admin"])
        return
    chemin = os.path.join(DATA_DIR, "users.json")
    if not os.path.exists(chemin):
        await repondre(update, "Aucun utilisateur.")
        return
    with open(chemin, "r", encoding="utf-8") as f:
        users = json.load(f)
    msg = "👥 Utilisateurs :\n\n"
    for uid, info in users.items():
        msg += f"ID: {uid}\nNom: {info.get('nom','')}\nUsername: @{info.get('username','')}\n\n"
    await repondre(update, msg[:4000])

# --- Commande admin /listeavis pour voir tous les avis ---
async def listeavis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await repondre(update, "❌ Vous n'êtes pas autorisé à utiliser cette commande.")
        return

    chemin_avis = "avis.json"
    if not os.path.exists(chemin_avis):
        await repondre(update, "Aucun avis n'a encore été envoyé.")
        return

    with open(chemin_avis, "r", encoding="utf-8") as f:
        try:
            avis_list = json.load(f)
        except Exception:
            await repondre(update, "Erreur lors de la lecture des avis.")
            return

    if not avis_list:
        await repondre(update, "Aucun avis n'a encore été envoyé.")
        return

    messages_avis = []
    for avis in avis_list:
        msg = f"👤 @{avis.get('username', 'inconnu')} (ID: {avis.get('user_id')}):\n" \
              f"📝 {avis.get('message')}\n" \
              f"📅 {avis.get('date')}\n\n"
        messages_avis.append(msg)

    max_len = 4000
    current_msg = ""
    for part in messages_avis:
        if len(current_msg) + len(part) > max_len:
            await update.message.reply_text(current_msg)
            current_msg = part
        else:
            current_msg += part
    if current_msg:
        await update.message.reply_text(current_msg)

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    texte_original = update.message.text.strip()
    texte = normaliser_nom(enlever_emojis(texte_original))
    log_message(user_id, f"Utilisateur: {texte_original}")
    sauvegarder_utilisateur(user)

    if await avis_message_handler(update, context):
        return

    if texte_original == "⬅️ Retour":
        user_states[user_id] = "menu"
        user_progress.pop(user_id, None)
        await start(update, context, message_personnalise=False)
        return

    # Ton code habituel pour gérer les QCM, sections, etc.
    # ...

    await repondre(update, messages["non_compris"])

def save_user_scores():
    chemin = "user_scores.json"
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(user_scores, f, ensure_ascii=False, indent=2)

user_scores = {}
if os.path.exists("user_scores.json"):
    with open("user_scores.json", "r", encoding="utf-8") as f:
        user_scores = json.load(f)

def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("avis", avis_command))  # Ajout commande /avis ici
    app.add_handler(CommandHandler("listeavis", listeavis))  # Commande admin pour voir les avis
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()

if __name__ == "__main__":
    if not os.path.exists("logs"):
        os.makedirs("logs")
    threading.Thread(target=lancer_flask).start()
    lancer_bot()
