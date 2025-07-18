class DéfiStates(StatesGroup):
    choix_niveau = State()
    choix_type = State()
    choix_matiere = State()
    choix_chapitre = State()
    concours_type = State()
    attente_joueur2 = State()
    defis_en_cours = State()
