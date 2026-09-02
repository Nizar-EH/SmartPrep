"""
Wrapper autour de l'API Google Gemini pour toutes les fonctionnalités
pédagogiques de l'application. Utilise le SDK officiel google-genai.
"""
import json
from google import genai
from google.genai import types
import config
import json
import re

# Modèle gratuit (voir aistudio.google.com/app/apikey pour la clé, et
# ai.google.dev/gemini-api/docs/pricing pour les modèles couverts par le
# palier gratuit). Change ici si tu veux essayer un autre modèle.
MODEL = "gemini-2.5-flash"


class AIClientError(Exception):
    pass


def _get_client():
    key = config.get_api_key()
    if not key:
        raise AIClientError(
            "Aucune clé API configurée. Va dans Paramètres pour ajouter ta clé Gemini."
        )
    return genai.Client(api_key=key)


def _ask(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    client = _get_client()
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=max_tokens,
            ),
        )
    except Exception as e:
        raise AIClientError(f"Erreur lors de l'appel à l'IA : {e}")

    text = getattr(response, "text", None)
    if not text:
        raise AIClientError("L'IA n'a renvoyé aucun contenu (réponse vide ou bloquée).")
    return text.strip()


def generate_revision_sheet(subject: str, course_content: str) -> str:
    """Génère une fiche de révision en Markdown à partir du contenu de cours fourni."""
    system = (
        "Tu es un professeur expérimenté qui crée des fiches de révision claires, "
        "structurées et efficaces pour des lycéens/étudiants. Réponds uniquement en "
        "Markdown : titres, listes à puces, mise en gras des notions clés, éventuels "
        "exemples courts. Sois synthétique mais complet sur les points essentiels."
    )
    user = (
        f"Matière : {subject}\n\n"
        f"Voici ce qui a été vu en cours (notes, résumés de séances, etc.) :\n"
        f"{course_content}\n\n"
        "Crée une fiche de révision structurée à partir de ce contenu."
    )
    return _ask(system, user, max_tokens=3000)


def generate_exercises(subject: str, instructions: str, source_content: str = "") -> str:
    """Génère des exercices en fonction d'une demande utilisateur (et éventuellement d'un contenu source)."""
    system = (
        "Tu es un professeur qui crée des exercices pédagogiques originaux, adaptés au "
        "niveau demandé. Formate ta réponse en Markdown, numérote les exercices "
        "clairement, et ne donne PAS le corrigé (l'élève le demandera séparément)."
    )
    user = f"Matière : {subject}\nDemande de l'élève : {instructions}\n"
    if source_content:
        user += f"\nContenu source à utiliser (cours, énoncé importé/scanné) :\n{source_content}\n"
    return _ask(system, user, max_tokens=3000)


def correct_exercise(subject: str, exercise_text: str, user_answer: str) -> str:
    """Fournit une correction méthodique de la réponse de l'élève."""
    system = (
        "Tu es un professeur qui corrige le travail d'un élève de façon méthodique et "
        "bienveillante. Pour chaque partie : indique si c'est correct, explique les "
        "erreurs précisément, donne la méthode/le raisonnement attendu, et propose la "
        "correction complète à la fin. Formate en Markdown."
    )
    user = (
        f"Matière : {subject}\n\nÉnoncé de l'exercice :\n{exercise_text}\n\n"
        f"Réponse de l'élève :\n{user_answer}\n\n"
        "Corrige cette réponse de façon méthodique."
    )
    return _ask(system, user, max_tokens=3000)


def feedback_evaluation(subject: str, title: str, grade: float, max_grade: float,
                         details: str = "") -> str:
    """Génère un feedback sur une évaluation : erreurs à éviter, techniques à améliorer."""
    system = (
        "Tu es un professeur qui aide un élève à progresser après une évaluation. "
        "Donne un feedback constructif : ce qui a probablement posé problème compte "
        "tenu de la note, les erreurs typiques à éviter dans ce type d'évaluation, et "
        "des techniques concrètes de méthode/révision pour la prochaine fois. "
        "Reste bienveillant et actionnable. Formate en Markdown."
    )
    user = (
        f"Matière : {subject}\nÉvaluation : {title}\nNote obtenue : {grade}/{max_grade}\n"
    )
    if details:
        user += f"\nDétails fournis par l'élève (points perdus, retours du professeur, etc.) :\n{details}\n"
    return _ask(system, user, max_tokens=2000)


def extract_evaluation_from_scan(raw_text: str) -> dict:
    """Extrait titre / note / date à partir du texte OCR d'une copie ou d'un
    bulletin scanné. Retourne un dict (clés potentiellement None si absentes) :
    title, grade, max_grade, date (YYYY-MM-DD), subject_guess.
    Retourne un dict vide si l'extraction échoue."""
    system = (
        "Tu extrais des informations structurées à partir du texte brut (OCR, donc "
        "parfois imparfait) d'une copie ou d'un bulletin scanné. Réponds UNIQUEMENT "
        "avec un objet JSON valide, sans texte ni balises markdown autour, avec "
        "exactement les clés : title (chaîne), grade (nombre ou null), "
        "max_grade (nombre ou null), date (chaîne YYYY-MM-DD ou null), "
        "subject_guess (chaîne ou null). Si une information est absente ou "
        "incertaine, mets null plutôt que d'inventer."
    )
    try:
        text = _ask(system, raw_text, max_tokens=500)
    except AIClientError:
        raise

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


def generate_exam_prep_plan(track_label: str, remaining_items: list, weak_subjects: list, days_left) -> str:
    """Génère un plan de révision priorisé pour un examen (Brevet/Bac), en
    tenant compte des épreuves restantes et des matières les plus faibles."""
    system = (
        "Tu es un conseiller pédagogique qui aide un élève français à préparer un "
        "examen (Brevet ou Bac). Donne un plan de révision concret et priorisé : "
        "quoi réviser en premier et pourquoi, comment répartir le temps entre les "
        "matières/épreuves restantes, et 2-3 conseils de méthode adaptés à cet "
        "examen précis. Sois concret et actionnable, pas générique. Formate en "
        "Markdown avec des sections courtes."
    )
    items_text = "\n".join(f"- {label} ({coef})" for _, label, coef in remaining_items)
    weak_text = ", ".join(weak_subjects) if weak_subjects else "aucune donnée de notes disponible"
    days_text = f"{days_left} jours" if days_left is not None else "date non précisée"

    user = (
        f"Examen préparé : {track_label}\n"
        f"Temps restant avant la première épreuve : {days_text}\n"
        f"Épreuves/matières restant à préparer :\n{items_text}\n\n"
        f"Matières où les moyennes sont les plus faibles actuellement : {weak_text}\n\n"
        "Construis un plan de révision priorisé."
    )
    return _ask(system, user, max_tokens=2000)


def extract_evaluation_from_scan(raw_text: str) -> dict:
    """Analyse le texte OCR d'une copie/bulletin scanné et tente d'en extraire
    le titre, la note, le barème et la date. Retourne un dict (clés manquantes
    ou incertaines à None). Retourne {} si l'extraction échoue complètement."""
    system = (
        "Tu extrais des informations structurées à partir du texte (issu d'un OCR, "
        "potentiellement imparfait) d'une copie ou d'un bulletin scanné. Réponds "
        "UNIQUEMENT avec un objet JSON valide, sans aucun texte autour ni balise de "
        "code, avec exactement ces clés : "
        '"title" (str ou null), "grade" (nombre ou null), "max_grade" (nombre ou null), '
        '"date" (string au format YYYY-MM-DD ou null), "subject_guess" (str ou null). '
        "Si une information est absente ou trop incertaine, mets null pour cette clé."
    )
    text = _ask(system, raw_text[:6000], max_tokens=500)

    cleaned = text.strip()
    # au cas où le modèle entoure quand même sa réponse de ```
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}
