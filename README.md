# SmartPrep

Un projet d''été qui est une application de bureau (PyQt6) utilisant l'IA (Google Gemini, gratuit)
pour t'aider dans tout ce qui est scolaire. Toutes les données restent en
local sur ta machine, dans `~/.schoolai/`.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate   # sous Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
python3 main.py
```

Au premier lancement, un écran te demande ton nom, ta classe et tes
matières (+ spécialités). Ensuite, va dans l'onglet **Paramètres** pour
coller ta clé API Google Gemini (gratuite, récupérable sur
https://aistudio.google.com/app/apikey — connexion avec un compte Google,
pas de carte bancaire nécessaire). Elle est stockée uniquement dans
`~/.schoolai/config.json`, jamais envoyée ailleurs que vers l'API Google
directement depuis ta machine.

Chaque personne qui utilise l'appli (toi, un ami...) doit créer sa propre
clé Gemini gratuite — ça évite de partager le même quota entre plusieurs
utilisateurs. Les données ne sont jamais partagées entre deux installations :
chaque machine a sa propre base locale.

## Fonctionnalités

### Accueil
Tableau de bord : évaluations à venir, matières à renforcer (d'après les
moyennes), et activité récente.

### Suivi examen 
Suivi spécialisé pour 3e (Brevet), 1ère (épreuves anticipées du Bac :
français + maths) et Terminale (Bac + Grand Oral) :
- **Détection automatique** du parcours à partir de ta classe (modifiable
  manuellement via le menu déroulant).
- **Checklist des épreuves** avec dates (pré-remplies à titre indicatif pour
  la session 2027, modifiables) et case à cocher une fois passées.
- **Compte à rebours** vers la prochaine échéance, visible aussi sur le
  tableau de bord d'accueil.
- **Plan de révision personnalisé** généré par l'IA, qui tient compte des
  épreuves restantes et de tes matières les plus faibles.
- **Préparation du Grand Oral (Terminale)** : sujets et questions choisis,
  notes de préparation, chronomètres d'entraînement (5 min exposé / 20 min
  entretien), génération de questions d'entraînement par l'IA.

### Emploi du temps interactif
- Ajoute une entrée à chaque heure de cours pour "nourrir" l'IA.
- **Emploi du temps type** : définis un modèle hebdomadaire réutilisable
  (bouton "Gérer l'emploi du temps type"), puis applique-le en un clic à
  n'importe quel jour ("Appliquer le modèle à ce jour").
- **Dupliquer hier** : recopie la structure (heures + matières) du jour
  précédent, pour compléter juste le contenu.
- **Vue semaine** : calendrier hebdomadaire cliquable.

### Fiches de révision
Génère une fiche structurée à partir du contenu de cours (chargé
automatiquement depuis l'emploi du temps, ou collé manuellement).
- Contenu éditable directement, avec bouton pour sauvegarder tes modifications.
- Bouton pour régénérer une nouvelle version.
- Export en PDF.

### Feedback sur les évaluations
- Enregistre une note et obtiens une analyse (erreurs à éviter, techniques
  à travailler). Feedback éditable et régénérable.
- **Import de scan** : importe une photo/PDF d'une copie ou d'un bulletin,
  l'IA essaie d'en extraire automatiquement le titre, la note et le
  barème pour pré-remplir le formulaire.
- **Évaluations à venir** : planifie tes prochaines évaluations (sous-onglet
  dédié), elles apparaissent ensuite sur le tableau de bord.
- Depuis un feedback, génère directement une fiche de révision ou des
  exercices ciblés sur les points faibles identifiés.

### Sandbox d'exercices
Génère des exercices via l'IA, ou importe un fichier (.txt, .pdf, image
scannée avec OCR si Tesseract est installé), réponds-y, puis demande une
correction méthodique. Correction éditable, régénérable, et tes réponses
précédentes sont rechargées si tu reviens sur un exercice.

### Statistiques
Évolution des notes et moyenne générale par trimestre.

### Paramètres
Clé API + **export/import de sauvegarde** de toutes tes données (un seul
fichier `.db` à transférer si tu changes d'ordinateur).

## OCR (scan d'exercices et d'évaluations) — optionnel

Pour scanner des PDF/images sans texte, installe en plus le binaire
Tesseract sur ta machine :

- macOS : `brew install tesseract tesseract-lang poppler`
- Ubuntu/Debian : `sudo apt install tesseract-ocr tesseract-ocr-fra poppler-utils`
- Windows : installeur officiel Tesseract + ajouter au PATH

## Structure du projet

```
schoolai/
  main.py                     # point d'entrée
  db.py                       # base de données SQLite locale
  config.py                   # stockage local de la clé API
  ai_client.py                # appels à l'API Gemini
  ocr_utils.py                # extraction de texte (import/scan)
  ui/
    onboarding.py             # écran de première ouverture
    main_window.py            # fenêtre principale + navigation
    dashboard_tab.py          # tableau de bord d'accueil
    schedule_tab.py           # emploi du temps interactif + vue semaine
    schedule_template_dialog.py  # gestion du modèle hebdomadaire
    revision_tab.py           # fiches de révision
    feedback_tab.py           # feedback évaluations + évaluations à venir
    sandbox_tab.py            # exercices (génération, import, correction)
    stats_tab.py              # graphiques
    settings_tab.py           # clé API + sauvegarde des données
    exam_tab.py                # suivi Brevet / Bac 1ère / Bac Terminale
  exam_tracks.py                # configuration des parcours d'examen
```

## Pistes d'amélioration restantes

- Édition/suppression fine des entrées d'emploi du temps et des matières.
- Rappels/notifications avant une évaluation à venir.
- Suppression/archivage des anciennes fiches et exercices.
