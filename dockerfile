# Utilise Python 3.10 comme image de base
FROM python:3.10-slim

# Définir le dossier de travail
WORKDIR /app

# Copier les fichiers dans l’image
COPY . .

# Installer les dépendances depuis requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Lancer ton bot
CMD ["python", "bot.py"]
