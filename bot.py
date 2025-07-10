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

# === CONFIGURATION GÉNÉRALE ===
DATA_DIR = "data"
SCORES_FILE = "user_scores.json"
user_states = {}
user_progress = {}
user_scores = {}
ADMIN_USER_ID = 6227031560
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Vérification token
if not BOT_TOKEN:
    print("🚨 ERREUR CRITIQUE : BOT_TOKEN non défini dans les variables d'environnement.")
    exit(1)

# === FLASK POUR RENDER ===
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Bot éducatif en ligne (Render + Flask + Telegram Bot)"

def lancer_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# === GESTION SCORES UTILISATEURS ===
def load_user_scores():
    if os.path.exists(SCORES_FILE):
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_user_scores():
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(user_scores, f, ensure_ascii=False, indent=2)

user_scores = load_user_scores()

# === FONCTIONS UTILES ===
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

# === CHARGEMENT DES MESSAGES ET CLAVIERS ===
messages = charger_json("messages.json")
intros = charger_json("intro.json")
claviers = charger_json("claviers.json")

# === START ===
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
        msg = messages.get("bienvenue", "Bienvenue!").replace("{nom}", nom)
        users[user_id]["bienvenue"] = True
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    else:
        msg = messages.get("retour", "Content de te revoir!") if message_personnalise else messages.get("choix", "Fais ton choix:")

    user_states[user.id] = "menu"
    user_progress.pop(user.id, None)
    log_message(user.id, "Commande /start")
    await repondre(update, msg, generer_clavier(claviers.get("menu_principal", [])))

# === HANDLER PRINCIPAL ===
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_id_str = str(user_id)
    texte_original = update.message.text.strip()
    texte = normaliser_nom(enlever_emojis(texte_original))
    log_message(user_id, f"Utilisateur: {texte_original}")
    sauvegarder_utilisateur(user)

    if texte_original == "⬅️ Retour":
        user_states[user_id] = "menu"
        user_progress.pop(user_id, None)
        await start(update, context, message_personnalise=False)
        return

    # Réponse QCM
    if user_id in user_states and user_states[user_id].startswith("qcm_"):
        state = user_states[user_id]
        prefix, matiere = "_".join(state.split("_")[1:-1]), state.split("_")[-1]
        fichier_qcm = f"{prefix}_{matiere}.json"
        qcm_data = charger_json(fichier_qcm)

        if not qcm_data or "qcm" not in qcm_data:
            await repondre(update, messages.get("qcm_introuvable", "QCM introuvable."), generer_clavier(["⬅️ Retour"]))
            user_states[user_id] = prefix
            return

        index = user_progress.get(user_id, 0)
        question = qcm_data["qcm"][index]
        options = question.get("options", [])
        bonne = question.get("reponse", "")

        texte_clean = normaliser_nom(enlever_emojis(texte_original).strip())
        options_clean = [normaliser_nom(enlever_emojis(opt).strip()) for opt in options]
        bonne_clean = normaliser_nom(enlever_emojis(bonne).strip())

        if texte_clean not in options_clean:
            await repondre(update, messages.get("choix_invalide", "Choix invalide."), generer_clavier(options + ["⬅️ Retour"]))
            return

        if user_id_str not in user_scores:
            user_scores[user_id_str] = {
                "nom": user.first_name,
                "actuel": {"total": 0, "correct": 0},
                "historique": []
            }

        user_scores[user_id_str]["nom"] = user.first_name
        user_scores[user_id_str]["actuel"]["total"] += 1

        if texte_clean == bonne_clean:
            await repondre(update, random.choice(messages.get("reponses_bonnes", ["Bonne réponse!"])))
            user_scores[user_id_str]["actuel"]["correct"] += 1
        else:
            mauvaise = random.choice([m.replace("{bonne}", bonne) for m in messages.get("reponses_mauvaises", ["Mauvaise réponse, la bonne était {bonne}."])])
            await repondre(update, mauvaise)

        if "explication" in question:
            await repondre(update, f"👉 {question['explication']}")

        user_progress[user_id] = random.randint(0, len(qcm_data["qcm"]) - 1)
        suivant = qcm_data["qcm"][user_progress[user_id]]
        await repondre(update, suivant['question'], generer_clavier(suivant.get("options", []) + ["⬅️ Retour"]))

        save_user_scores()
        return

    # Commandes de navigation
    if texte in ["/start", "start", "demarrer", "démarrer"]:
        await start(update, context)
        return

    if texte_original == "Quitter le bot":
        nom = user.first_name or user.full_name or "cher utilisateur"
        await repondre(update, messages.get("quitter", "Au revoir {nom}!").replace("{nom}", nom), generer_clavier(["Démarrer"]))
        user_states.pop(user_id, None)
        user_progress.pop(user_id, None)
        return

    # Sections statiques
    section_static = {
        "informations": "informations.json",
        "infos": "informations.json",
        "info": "informations.json",
        "profil": "espace.json",
        "espace": "espace.json",
        "compte": "espace.json"
    }

    if texte in section_static:
        cle = texte
        user_states[user_id] = cle
        data = charger_json(section_static[cle])
        await repondre(update, data.get("message", "Aucune donnée disponible."), generer_clavier(["⬅️ Retour"]))
        increment_stat(f"static_{cle}")
        return

    # Sections dynamiques
    choix_sections = {
        "bepc": "bepc.json",
        "bac_a": "bac_a.json",
        "bac_c": "bac_c.json",
        "bac_d": "bac_d.json",
        "concours": "concours.json",
        "technique": None,
    }

    if texte in choix_sections:
        user_states[user_id] = texte
        if texte == "technique":
            await repondre(update, messages.get("technique_indisponible", "Section technique indisponible."), generer_clavier(["⬅️ Retour"]))
            return
        data = charger_json(choix_sections[texte])
        matieres = data.get("matieres", [])
        msg = intros.get(texte, "") + "\n\n" + data.get("message", "Choisis une matière :")
        increment_stat(f"section_{texte}")
        await repondre(update, msg.strip(), generer_clavier(matieres + ["⬅️ Retour"]))
        return

    if matiere == "superieur_a_bac":
            data = charger_json("concours_superieur_a_bac.json")
            if "message" in data:
                await repondre(update, data["message"], generer_clavier(["⬅️ Retour"]))
            else:
                await repondre(update, messages.get("qcm_introuvable", "QCM introuvable."), generer_clavier(["⬅️ Retour"]))
            return

    # Lancement d’un QCM par matière
    if user_id in user_states and user_states[user_id] in choix_sections:
        prefix = normaliser_nom(user_states[user_id])
        matiere = normaliser_nom(enlever_emojis(texte_original))
        fichier_qcm = f"{prefix}_{matiere}.json"
        qcm_data = charger_json(fichier_qcm)
        increment_stat(f"matiere_{prefix}_{matiere}")

        if "qcm" in qcm_data and qcm_data["qcm"]:
            user_states[user_id] = f"qcm_{prefix}_{matiere}"
            user_progress[user_id] = 0
            question = qcm_data["qcm"][0]
            await repondre(update, question["question"], generer_clavier(question.get("options", []) + ["⬅️ Retour"]))
        else:
            await repondre(update, messages.get("qcm_introuvable", "QCM introuvable."), generer_clavier(["⬅️ Retour"]))
        return

    # === Aucun cas reconnu ===
    await repondre(update, messages["non_compris"])

# === COMMANDES SUPPLÉMENTAIRES ===

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Accès réservé à l'administrateur.")
        return

    if not context.args:
        await update.message.reply_text("Usage : /broadcast <message>")
        return

    message = " ".join(context.args)
    users_path = os.path.join(DATA_DIR, "users.json")
    if not os.path.exists(users_path):
        await update.message.reply_text("Aucun utilisateur enregistré.")
        return

    with open(users_path, "r", encoding="utf-8") as f:
        users = json.load(f)

    success = 0
    failed = 0
    for uid in users.keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=message)
            success += 1
        except Exception:
            failed += 1

    await update.message.reply_text(f"Message envoyé à {success} utilisateurs, échec pour {failed}.")

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Accès réservé à l'administrateur.")
        return

    users_path = os.path.join(DATA_DIR, "users.json")
    if not os.path.exists(users_path):
        await update.message.reply_text("Aucun utilisateur enregistré.")
        return

    with open(users_path, "r", encoding="utf-8") as f:
        users = json.load(f)

    msg = "👥 Liste des utilisateurs enregistrés :\n"
    for uid, data in users.items():
        nom = data.get("nom", "")
        username = data.get("username", "")
        msg += f"- {nom} (@{username}) [ID: {uid}]\n"

    await update.message.reply_text(msg[:4000])

# === DÉMARRAGE DU BOT ===

def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profil", profil))
    app.add_handler(CommandHandler("reset_profil", reset_profil))
    app.add_handler(CommandHandler("admin_scores", admin_scores))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("listusers", listusers))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling()

# === POINT D’ENTRÉE ===

if __name__ == "__main__":
    if not os.path.exists("logs"):
        os.makedirs("logs")

    threading.Thread(target=lancer_flask).start()
    lancer_bot()
