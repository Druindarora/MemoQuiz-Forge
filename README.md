# MemoQuiz Forge

Outil local de préparation, contrôle et export de questions pour MemoQuiz.

## Installation locale

Depuis un clone neuf, créer puis activer un environnement virtuel :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Installer le projet en mode editable :

```bash
python -m pip install --editable .
```

## Initialiser la base locale

```bash
memoquiz-forge init
```

La commande crée la base SQLite dans `data/memoquiz-forge.db`.

## Exécuter les tests

```bash
PYTHONPATH=src python -m unittest discover -v
```
