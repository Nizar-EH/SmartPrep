"""
Configuration des parcours d'examen : Brevet (3e), épreuves anticipées du Bac
(1ère), Bac + Grand Oral (Terminale). Dates indicatives pour la session 2027
(année scolaire 2026-2027) — à ajuster par l'utilisateur si son académie ou
son année diffère.
"""

TRACKS = {
    "brevet": "Brevet des collèges (3e)",
    "bac_premiere": "Bac de français (1ère)",
    "bac_terminale": "Bac + Grand Oral (Terminale)",
}


def detect_track_from_classe(classe: str) -> str | None:
    """Essaie de deviner le parcours à partir du texte libre de la classe."""
    if not classe:
        return None
    c = classe.lower()
    if "3e" in c or "3è" in c or "troisi" in c:
        return "brevet"
    if "1ere" in c or "1ère" in c or "premi" in c:
        return "bac_premiere"
    if "term" in c or "tle" in c:
        return "bac_terminale"
    return None


# Chaque item : (clé, libellé, date indicative YYYY-MM-DD ou None, coefficient info)
CHECKLISTS = {
    "brevet": [
        ("francais_ecrit", "Français — écrit (3h)", "2027-06-24", "coef 2"),
        ("maths_ecrit", "Mathématiques — écrit", "2027-06-24", "coef 2"),
        ("histoire_geo_emc", "Histoire-Géographie-EMC — écrit", "2027-06-25", "coef 1,5 + 0,5"),
        ("sciences_ecrit", "Sciences (2 matières tirées au sort sur 3) — écrit (1h)", "2027-06-28", "coef 2"),
        ("oral_soutenance", "Oral de soutenance de projet (15 min)", None, "coef 2"),
        ("controle_continu", "Contrôle continu (moyennes de l'année de 3e)", None, "40% de la note finale"),
    ],
    "bac_premiere": [
        ("francais_ecrit", "Français — écrit (4h)", "2027-06-15", "épreuve anticipée"),
        ("francais_oral", "Français — oral (date fixée par l'académie)", None, "épreuve anticipée"),
        ("maths_anticipee", "Mathématiques — épreuve anticipée (si tu n'as pas gardé maths en spécialité)", "2027-06-21", "nouveauté depuis 2027"),
    ],
    "bac_terminale": [
        ("spe1_ecrit", "1ère spécialité — écrit", "2027-06-16", "coef 16 à elles deux"),
        ("spe2_ecrit", "2e spécialité — écrit", "2027-06-17", "coef 16 à elles deux"),
        ("philo_ecrit", "Philosophie — écrit (4h)", "2027-06-14", "coef 8 (générale) / 4 (techno)"),
        ("grand_oral", "Grand Oral", "2027-06-21", "coef 10 (générale) / 14 (techno)"),
        ("controle_continu", "Contrôle continu (bulletins 1ère + Terminale, EPS...)", None, "40% de la note finale"),
    ],
}

NOTES = {
    "brevet": (
        "Depuis la réforme 2026 : note finale sur 20, 40% de contrôle continu "
        "(moyenne de toutes les matières de 3e à poids égal) + 60% d'épreuves "
        "terminales. Priorise Français et Maths, coefficients les plus élevés."
    ),
    "bac_premiere": (
        "Ces épreuves anticipées comptent pour environ 5% de la note finale du "
        "Bac. L'épreuve de maths anticipée ne concerne que les élèves qui "
        "n'ont pas gardé la spécialité mathématiques en Terminale."
    ),
    "bac_terminale": (
        "Le contrôle continu compte pour 40% de la note finale. Les épreuves "
        "terminales (spécialités + philo + grand oral) comptent pour 60%. "
        "Les deux spécialités représentent à elles seules 32 des 60 points."
    ),
}
