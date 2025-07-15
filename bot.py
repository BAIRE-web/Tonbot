import os, json, unicodedata, random, re, threading
from datetime import datetime
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.error import Forbidden

DATA_DIR = "data"
LOG_DIR = "logs"
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_USER_ID = 6227031560

user_states, user_progress, user_states_avis = {}, {}, set()
user_scores = {}

flask_app = Flask(__name__)
@flask_app.route("/")
def home():
    return "✅ Bot éducatif en ligne (Render + Flask + Telegram Bot)"

def lancer_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def chemin_data(fichier): return os.path.join(DATA_DIR, fichier)

def charger_json(fichier):
    chemin = chemin_data(fichier)
    if os.path.exists(chemin):
        with open(chemin, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {}
    return {}

def sauvegarder_json(fichier, data):
    with open(chemin_data(fichier), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def enlever_emojis(text):
    pattern = re.compile("["
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
    return pattern.sub('', text).strip()

def normaliser_nom(nom):
    return unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode("utf-8").lower().replace(" ", "_")

def log_message(user_id, message):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, f"{user_id}.txt"), "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")

def increment_stat(cle):
    stats = {}
    chemin = "stats.json"
    if os.path.exists(chemin):
        with open(chemin, "r", encoding="utf-8") as f:
            try: stats = json.load(f)
            except: stats = {}
    stats[cle] = stats.get(cle, 0) + 1
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def sauvegarder_utilisateur(user):
    chemin = chemin_data("users.json")
    users = charger_json("users.json")
    uid = str(user.id)
    if uid not in users:
        users[uid] = {"username": user.username or "", "nom": user.full_name or "", "bienvenue": False}
    else:
        users[uid]["username"] = user.username or users[uid].get("username", "")
        users[uid]["nom"] = user.full_name or users[uid].get("nom", "")
    sauvegarder_json("users.json", users)

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
    users = charger_json("users.json")
    deja_accueilli = users.get(user_id, {}).get("bienvenue", False)
    nom = user.first_name or user.full_name or "cher utilisateur"
    if not deja_accueilli:
        msg = messages.get("bienvenue", "").replace("{nom}", nom)
        users[user_id]["bienvenue"] = True
        sauvegarder_json("users.json", users)
    else:
        msg = messages.get("retour", "") if message_personnalise else messages.get("choix", "")
    user_states[user.id] = "menu"
    user_progress.pop(user.id, None)
    log_message(user.id, "Commande /start")
    await repondre(update, msg, generer_clavier(claviers.get("menu_principal", [])))

async def avis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_states_avis.add(update.effective_user.id)
    await update.message.reply_text("Quel est votre avis ou suggestion ?")

async def avis_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states_avis:
        return False
    texte = update.message.text.strip()
    chemin_avis = "avis.json"
    avis_list = []
    if os.path.exists(chemin_avis):
        with open(chemin_avis, "r", encoding="utf-8") as f:
            try: avis_list = json.load(f)
            except: avis_list = []
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
        await repondre(update, messages.get("non_admin", ""))
        return
    msg = " ".join(context.args)
    if not msg:
        await repondre(update, "Utilise : /broadcast <message>")
        return
    users = charger_json("users.json")
    if not users:
        await repondre(update, "Aucun utilisateur.")
        return
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
        await repondre(update, messages.get("non_admin", ""))
        return
    users = charger_json("users.json")
    if not users:
        await repondre(update, "Aucun utilisateur.")
        return
    msg = "👥 Utilisateurs :\n\n" + "\n\n".join(
        f"ID: {uid}\nNom: {info.get('nom','')}\nUsername: @{info.get('username','')}"
        for uid, info in users.items()
    )
    await repondre(update, msg[:4000])

async def listeavis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await repondre(update, "❌ Vous n'êtes pas autorisé à utiliser cette commande.")
        return
    if not os.path.exists("avis.json"):
        await repondre(update, "Aucun avis n'a encore été envoyé.")
        return
    with open("avis.json", "r", encoding="utf-8") as f:
        try:
            avis_list = json.load(f)
        except:
            await repondre(update, "Erreur lors de la lecture des avis.")
            return
    if not avis_list:
        await repondre(update, "Aucun avis n'a encore été envoyé.")
        return
    max_len, current_msg = 4000, ""
    for avis in avis_list:
        part = f"👤 @{avis.get('username', 'inconnu')} (ID: {avis.get('user_id')}):\n📝 {avis.get('message')}\n📅 {avis.get('date')}\n\n"
        if len(current_msg) + len(part) > max_len:
            await update.message.reply_text(current_msg)
            current_msg = part
        else:
            current_msg += part
    if current_msg:
        await update.message.reply_text(current_msg)

async def reset_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    scores = user_scores.get(user_id)
    if not scores or scores["actuel"]["total"] == 0:
        await update.message.reply_text("Tu n'as aucun score actuel à réinitialiser.")
        return
    historique = scores.get("historique", [])
    historique.append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": scores["actuel"]["total"],
        "correct": scores["actuel"]["correct"]
    })
    scores["actuel"] = {"total": 0, "correct": 0}
    scores["historique"] = historique
    user_scores[user_id] = scores
    sauvegarder_json("user_scores.json", user_scores)
    await update.message.reply_text("✅ Ton score a été réinitialisé, mais l'historique est conservé.")

async def historique(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    scores = user_scores.get(user_id)
    if not scores or not scores.get("historique"):
        await update.message.reply_text("Aucun historique de score trouvé.")
        return
    historique = scores["historique"]
    msg = "📊 Historique de tes scores :\n\n"
    for i, entry in enumerate(historique[-5:], 1):
        total = entry["total"]
        correct = entry["correct"]
        pourcentage = round((correct / total) * 100, 2) if total else 0
        msg += f"{i}. 📅 {entry['date']} - ✅ {correct}/{total} → {pourcentage}%\n"
    await update.message.reply_text(msg)

async def profil_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in user_scores:
        await repondre(update, "Aucun score enregistré pour vous.")
        return
    score = user_scores[uid]["actuel"]
    total, correct = score["total"], score["correct"]
    pourcentage = (correct / total * 100) if total else 0
    msg = f"📊 *Votre score actuel :*\n\n✔️ Correctes : {correct}\n❌ Total : {total}\n🎯 Précision : {pourcentage:.1f}%"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def scores_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await repondre(update, "❌ Vous n'avez pas l'autorisation.")
        return
    if not user_scores:
        await repondre(update, "Aucun score n'a encore été enregistré.")
        return
    msg = "📈 *Scores des utilisateurs :*\n\n"
    count = 0
    for uid, data in user_scores.items():
        score = data.get("actuel", {})
        correct = score.get("correct", 0)
        total = score.get("total", 0)
        if total == 0:
            continue
        pourcentage = correct / total * 100
        nom = data.get("nom", f"ID:{uid}")
        msg += f"{nom} → {correct}/{total} ({pourcentage:.1f}%)\n"
        count += 1
        if count >= 30:
            break
    await update.message.reply_text(msg, parse_mode="Markdown")

def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("avis", avis_command))
    app.add_handler(CommandHandler("listeavis", listeavis))
    app.add_handler(CommandHandler("reset_score", reset_score))
    app.add_handler(CommandHandler("historique", historique))
    app.add_handler(CommandHandler("profil", profil_command))
    app.add_handler(CommandHandler("scores", scores_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    threading.Thread(target=lancer_flask).start()
    app.run_polling()
