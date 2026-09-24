# MemoQuiz Forge

MemoQuiz Forge est un outil local en ligne de commande pour préparer une banque de questions destinée à [MemoQuiz](https://memoquiz.com/). Il ne gère ni les quiz ni la progression : il permet de créer, organiser, contrôler, importer et exporter des questions.

Les données restent sur votre machine, dans une base SQLite locale.

## Prérequis et installation

Il faut Python **3.11 ou supérieur**.

Depuis un clone neuf, créez et activez un environnement virtuel :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Installez ensuite l'outil :

```bash
python -m pip install --editable .
```

Initialisez la base locale, une seule fois par dossier de travail :

```bash
memoquiz-forge init
```

Cette commande crée `data/memoquiz-forge.db`. Les commandes suivantes utilisent cette base dans le dossier courant : exécutez-les donc depuis le même dossier.

## Aide intégrée

Pour afficher toutes les commandes :

```bash
memoquiz-forge --help
```

Chaque commande possède sa propre aide. Par exemple :

```bash
memoquiz-forge export --help
```

`-h` est un raccourci de `--help`.

## Cycle d'utilisation courant

1. Ajoutez des questions une par une ou importez un fichier JSON.
2. Complétez leurs métadonnées avec `edit` si besoin.
3. Validez les questions complètes.
4. Exportez les questions validées dans un fichier JSON à importer dans MemoQuiz.

## Commandes

### Créer la base locale

```bash
memoquiz-forge init
```

Crée la base SQLite locale si elle n'existe pas encore.

### Ajouter une question

```bash
memoquiz-forge add --question "Qu'est-ce qu'un index SQL ?" \
  --answer "Une structure qui accélère certaines recherches." \
  --domain sql --concept indexes --level basic \
  --tag database --tag performance
```

Arguments :

- `--question TEXTE` — obligatoire ; texte non vide de la question.
- `--answer TEXTE` — obligatoire ; texte non vide de la réponse.
- `--domain TEXTE` — optionnel ; domaine technique, par exemple `angular`, `java`, `sql` ou `git`.
- `--concept TEXTE` — optionnel ; sujet précis, par exemple `indexes` ou `component-communication`.
- `--level basic|intermediate|advanced` — optionnel ; niveau de difficulté.
- `--tag TEXTE` — optionnel et répétable.

Une question ajoutée est toujours créée avec le statut `draft` et comme non exportée. Les doublons exacts sont refusés ; une même question avec une réponse différente est acceptée mais signalée.

### Lister les questions

```bash
memoquiz-forge list
memoquiz-forge list --status draft --domain angular --unexported
```

Affiche une ligne concise par question, sans afficher sa réponse complète.

Filtres combinables :

- `--status draft|validated|rejected`
- `--domain TEXTE`
- `--concept TEXTE`
- `--level basic|intermediate|advanced`
- `--unexported` — limite aux questions qui n'ont jamais été produites dans un export Forge.

### Afficher une question

```bash
memoquiz-forge show 12
```

Affiche le texte, la réponse, les tags, les métadonnées, le statut et les dates de la question `12`.

### Modifier une question

```bash
memoquiz-forge edit 12 \
  --domain angular \
  --concept component-communication \
  --level basic \
  --tag input --tag output
```

Les options disponibles sont `--question`, `--answer`, `--domain`, `--concept`, `--level` et `--tag`. Seuls les champs fournis sont modifiés.

Attention : si au moins un `--tag` est fourni, la liste complète des tags existants est remplacée par les tags indiqués. Les niveaux possibles sont `basic`, `intermediate` et `advanced`.

### Valider ou rejeter une question

```bash
memoquiz-forge validate 12
memoquiz-forge reject 12
```

`validate` exige une question, une réponse, un domaine, un concept et un niveau renseignés. Les tags restent facultatifs. Une question déjà validée ne change pas. `reject` marque une question comme rejetée sans supprimer son contenu.

### Valider plusieurs brouillons

```bash
memoquiz-forge validate-all
memoquiz-forge validate-all --domain angular --level basic
```

Traite uniquement les questions au statut `draft`. Les brouillons complets passent à `validated` ; les autres restent inchangés et sont listés avec leurs champs manquants.

Filtres combinables : `--domain TEXTE`, `--concept TEXTE` et `--level basic|intermediate|advanced`.

### Importer un fichier JSON

```bash
memoquiz-forge import questions.json
```

Le fichier doit être un tableau JSON. Le format minimal compatible avec MemoQuiz est :

```json
[
  {
    "question": "Qu'est-ce qu'un composant Angular ?",
    "answer": "Un bloc de construction de l'interface utilisateur."
  }
]
```

Le format enrichi accepte également `domain`, `concept`, `level` et `tags` :

```json
[
  {
    "question": "Comment un parent transmet-il une valeur à un enfant ?",
    "answer": "Avec un input.",
    "domain": "angular",
    "concept": "component-communication",
    "level": "basic",
    "tags": ["input", "components"]
  }
]
```

Règles du fichier :

- `question` et `answer` sont obligatoires et doivent être des chaînes non vides.
- `domain` et `concept`, s'ils sont présents, doivent être des chaînes.
- `level`, s'il est présent, doit être `basic`, `intermediate` ou `advanced`.
- `tags`, s'il est présent, doit être un tableau de chaînes.
- N'incluez pas `id`, `status`, `exported`, les dates ou les fingerprints : Forge les gère lui-même et refusera le fichier.

L'import valide tout le fichier avant toute écriture. Toutes les entrées importées deviennent des brouillons non exportés. Les doublons exacts sont ignorés et comptés dans le résumé ; les conflits de question avec une réponse différente sont importés et signalés.

### Exporter vers MemoQuiz

```bash
memoquiz-forge export memoquiz-import.json --count 20
memoquiz-forge export angular-basic.json --count 20 --domain angular --level basic
```

Arguments et options :

- `FICHIER.json` — chemin du fichier JSON à créer.
- `--count N` — obligatoire ; entier strictement positif, correspondant au nombre maximal de questions à exporter.
- `--domain TEXTE`, `--concept TEXTE`, `--level basic|intermediate|advanced` — filtres optionnels et combinables.
- `--force` — autorise l'écrasement d'un fichier de destination existant.

Seules les questions `validated` et jamais exportées sont sélectionnées, par ordre d'identifiant croissant. Si moins de questions sont disponibles que demandé, toutes les questions disponibles sont exportées.

Le fichier produit est du JSON UTF-8 lisible, ne contenant strictement que `question` et `answer` :

```json
[
  {
    "question": "Question 1",
    "answer": "Réponse 1"
  }
]
```

Après une écriture réussie, les questions présentes dans ce fichier sont marquées comme exportées. Cela signifie uniquement qu'elles ont déjà été produites dans un export Forge ; Forge ne vérifie pas qu'elles ont ensuite été importées dans MemoQuiz.

## Sorties et erreurs fréquentes

- La base de travail est `data/memoquiz-forge.db`.
- Les fichiers d'export sont créés exactement au chemin donné à la commande `export`.
- Si aucune question ne correspond à une recherche, `list` affiche `No questions found.`.
- Si aucune question validée non exportée ne correspond à un export, aucun fichier vide n'est créé et l'outil affiche `No questions available for export.`.
- Un fichier d'export déjà existant est protégé par défaut. Choisissez un nouveau nom ou ajoutez `--force` pour l'écraser explicitement.
- Les identifiants affichés par `list` sont ceux à fournir à `show`, `edit`, `validate` et `reject`.
- Une validation refusée indique les champs manquants ; corrigez-les avec `edit`, puis réessayez.

## Tests

Depuis l'environnement virtuel :

```bash
PYTHONPATH=src python -m unittest discover -v
```
