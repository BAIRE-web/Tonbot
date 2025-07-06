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

# === Variables globales ===
DATA_DIR = "data"
user_states = {}
user_progress = {}
ADMIN_USER_ID = 6227031560
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # ✅ Sécurité : token via variable d'environnement

# === Création du serveur Flask ===
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Bot éducatif en ligne (Render + Flask + Telegram Bot)"

def lancer_flask():
    port = int(os.environ.get("PORT", 10000))  # Pour Render
    flask_app.run(host="0.0.0.0", port=port)

def enlever_emojis(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticônes
        "\U0001F300-\U0001F5FF"  # symboles et pictogrammes
        "\U0001F680-\U0001F6FF"  # transport et symboles
        "\U0001F1E0-\U0001F1FF"  # drapeaux (lettres régionales)
        "\U00002700-\U000027BF"  # divers symboles
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

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
        users[uid] = {
            "username": user.username or "",
            "nom": user.full_name or "",
            "bienvenue": False
        }
    else:
        users[uid]["username"] = user.username or users[uid].get("username", "")
        users[uid]["nom"] = user.full_name or users[uid].get("nom", "")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def generer_clavier(options):
    return ReplyKeyboardMarkup([[opt] for opt in options], resize_keyboard=True)

async def repondre(update: Update, message: str, clavier=None):
    user_id = update.effective_user.id
    log_message(user_id, f"Bot: {message}")
    await update.message.reply_text(message, reply_markup=clavier)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, message_personnalise=True):
    user = update.effective_user
    user_id = str(user.id)
    sauvegarder_utilisateur(user)

    chemin = os.path.join(DATA_DIR, "users.json")
    with open(chemin, "r", encoding="utf-8") as f:
        users = json.load(f)

    deja_accueilli = users[user_id].get("bienvenue", False)

    if not deja_accueilli:
        nom = user.first_name or user.full_name or "cher utilisateur"
        msg = f"‎✨ Mes salutations {nom} !\nBienvenue sur notre bot éducatif. Chaque option vous conduit à une suite personnalisée.\n‎↩️ Pour revenir au menu principal ou quitter une formation, utilisez simplement le bouton « Retour ».\n\nChoisis une option :"
        users[user_id]["bienvenue"] = True
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    else:
        if message_personnalise:
            msg = "🎉 Bon retour, Mes salutations !\n‎⚡ Prêt(e) pour une nouvelle expérience ? \n\nChoisis une option :"
        else:
            msg = "Choisis une option pour continuer :"

    user_states[user.id] = "menu"
    user_progress.pop(user.id, None)
    log_message(user.id, "Commande /start")
    await repondre(update, msg,
        generer_clavier([
            "Informations", "Espace", "BEPC", "Bac A", "Bac C", "Bac D", "Concours", "Technique", "Quitter le bot"
        ])
    )

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await repondre(update, "Fonction non reconnue, merci de faire un choix valide.")
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
    await repondre(update, f"Message envoyé avec succes à {count} utilisateur(s).")

async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_USER_ID:
        await repondre(update, "Fonction non reconnue, merci de faire un choix valide.")
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

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    texte = update.message.text.strip()
    log_message(user_id, f"Utilisateur: {texte}")
    sauvegarder_utilisateur(user)

    if texte == "⬅️ Retour":
        user_states[user_id] = "menu"
        user_progress.pop(user_id, None)
        await start(update, context, message_personnalise=False)
        return

    if user_id in user_states and user_states[user_id].startswith("qcm_"):
        state = user_states[user_id]
        parts = state.split("_")
        prefix = "_".join(parts[1:-1])
        matiere = parts[-1]
        fichier_qcm = f"{prefix}_{matiere}.json"
        qcm_data = charger_json(fichier_qcm)

        if not qcm_data or "qcm" not in qcm_data:
            await repondre(update, "Pas de QCM trouvé. Merci de renouveler votre choix.", generer_clavier(["⬅️ Retour"]))
            user_states[user_id] = prefix
            return

        index = user_progress.get(user_id, 0)
        qcm_list = qcm_data["qcm"]
        question = qcm_list[index]
        options = question.get("options", [])
        bonne = question.get("reponse", "")

        if texte not in options:
            await repondre(update, "Choix invalide, veuillez réessayer.", generer_clavier(options + ["⬅️ Retour"]))
            return

        # Nettoyage des emojis avant comparaison
        texte_sans_emoji = enlever_emojis(texte).strip()
        bonne_sans_emoji = enlever_emojis(bonne).strip()

        if normaliser_nom(texte_sans_emoji) == normaliser_nom(bonne_sans_emoji):
            bonne_reponses_possibles = [
                "🎉 Félicitations 🙂 c'est la bonne réponse !",
                "✅ Bonne réponse, tu gères ça !",
                "👏 Bravo, c’est exactement ça !",
                "🎯 Tu as visé juste, bien joué !",
                "🌟 Excellente réponse, continue comme ça !"
            ]
            await repondre(update, random.choice(bonne_reponses_possibles))
        else:
            mauvaises_reponses_possibles = [
                f"😕 Oups, ce n’est pas la bonne réponse ❌.\n👉 La bonne réponse était : {bonne}",
                f"🙂 Tu étais presque, hélas ce n’est pas la bonne réponse ❌.\n👉 La bonne réponse était : {bonne}",
                f"❌ Raté cette fois ! La bonne réponse était : {bonne}",
                f"🙁 Dommage, ce n’était pas ça. 👉 Réponse attendue : {bonne}",
                f"🧐 Mauvaise pioche ! La bonne réponse était : {bonne}"
            ]
            await repondre(update, random.choice(mauvaises_reponses_possibles))

        explication = question.get("explication", "")
        if explication:
            await repondre(update, f"👉 Une brève explication pour toi : {explication}")

        user_progress[user_id] = random.randint(0, len(qcm_list) - 1)
        suivant = qcm_list[user_progress[user_id]]
        await repondre(update, f"{suivant['question']}", generer_clavier(suivant.get("options", []) + ["⬅️ Retour"]))
        return

    if texte == "Quitter le bot":
        nom = user.first_name or user.full_name or "cher utilisateur"
        msg = f"‎🙏Merci de vous être formé avec nous, ce fut un plaisir de vous accompagner.\n‎🔔 N’hésitez pas à revenir quand vous voulez.\n‎🍀 Bonne continuation, {nom} !"
        await repondre(update, msg, generer_clavier(["Démarrer"]))
        user_states.pop(user_id, None)
        user_progress.pop(user_id, None)
        return

    if texte.lower() == "démarrer" or texte.lower() in ["/start", "start"]:
        await start(update, context)
        return

    if texte.lower() in ["informations", "infos", "info"]:
        user_states[user_id] = "infos"
        data = charger_json("informations.json")
        await repondre(update, data.get("message", "Aucune information disponible."), generer_clavier(["⬅️ Retour"]))
        increment_stat("infos")
        return

    if texte.lower() in ["espace", "profil", "compte"]:
        user_states[user_id] = "espace"
        data = charger_json("espace.json")
        await repondre(update, data.get("message", "Aucune donnée dans l'espace utilisateur."), generer_clavier(["⬅️ Retour"]))
        increment_stat("espace")
        return

    choix_sections = {
        "bepc": "bepc.json",
        "bac a": "bac_a.json",
        "bac c": "bac_c.json",
        "bac d": "bac_d.json",
        "concours": "concours.json",
        "technique": None,
    }

    texte_normalise = texte.lower()

    if texte_normalise in choix_sections:
        if texte_normalise == "technique":
            await repondre(update, "🔧 Option Technique bientôt disponible...", generer_clavier(["⬅️ Retour"]))
            return
        user_states[user_id] = texte_normalise
        fichier = choix_sections[texte_normalise]
        data = charger_json(fichier)
        matieres = data.get("matieres", [])
        msg = data.get("message", "Choisis une matière :")
        increment_stat(f"section_{texte_normalise}")

        intro_messages = {
            "concours": "🎯 ‎📋 Lors d’un concours, vous avez 50 QCM à traiter, couvrant tout ce qui concerne ce niveau : culture générale, tests psychotechniques, dans un ordre un peu aléatoire.\n‎🚀 Après le choix de votre niveau, nous commencerons à vous former spécifiquement pour ce concours.! \nChoisis un niveau pour consulter les matières 👇",
            "bepc": "‎📌 La révision se fait par matières, pas par chapitres, car à l’examen, on ne sait pas ce qui tombera précisément.\n‎🎲 Une fois une matière choisie, une série aléatoire de QCM vous sera proposée, comme à l’examen.",
            "bac a": "📘 Tu as choisi la section BAC A. ‎📌 La révision se fait par matières, pas par chapitres, car à l’examen, on ne sait pas ce qui tombera précisément.\n‎🎲 Une fois une matière choisie, une série aléatoire de QCM vous sera proposée, comme à l’examen. :",
            "bac c": "🧪 Bienvenue en BAC C. ‎📌 La révision se fait par matières, pas par chapitres, car à l’examen, on ne sait pas ce qui tombera précisément.\n‎🎲 Une fois une matière choisie, une série aléatoire de QCM vous sera proposée, comme à l’examen. :",
            "bac d": "🔬 Tu es dans la section BAC D. ‎📌 La révision se fait par matières, pas par chapitres, car à l’examen, on ne sait pas ce qui tombera précisément.\n‎🎲 Une fois une matière choisie, une série aléatoire de QCM vous sera proposée, comme à l’examen. :",
        }
        if texte_normalise in intro_messages:
            await repondre(update, intro_messages[texte_normalise])
        await repondre(update, msg, generer_clavier(matieres + ["⬅️ Retour"]))
        return

    if user_id in user_states and user_states[user_id] in choix_sections:
        prefix = normaliser_nom(user_states[user_id])
        matiere = normaliser_nom(texte)
        fichier_qcm = f"{prefix}_{matiere}.json"
        qcm_data = charger_json(fichier_qcm)
        increment_stat(f"matiere_{prefix}_{matiere}")
        if "qcm" in qcm_data and qcm_data["qcm"]:
            user_states[user_id] = f"qcm_{prefix}_{matiere}"
            user_progress[user_id] = 0
            question = qcm_data["qcm"][0]
            await repondre(update, f"{question['question']}", generer_clavier(question.get("options", []) + ["⬅️ Retour"]))
        else:
            await repondre(update, "Aucun QCM trouvé. Merci de renouveler votre choix.", generer_clavier(["⬅️ Retour"]))
        return

    await repondre(update, "Option non reconnue. Tape /start pour recommencer.")

def lancer_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.run_polling()

# === Lancement parallèle Flask + Bot Telegram ===
if __name__ == "__main__":
    if not os.path.exists("logs"):
        os.makedirs("logs")
    threading.Thread(target=lancer_flask).start()
    lancer_bot()
