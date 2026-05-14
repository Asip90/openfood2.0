# Migration SQLite → PostgreSQL

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer SQLite par PostgreSQL en local et sur Render, sans toucher au code métier.

**Architecture:** On utilise `dj-database-url` pour lire une `DATABASE_URL` depuis l'environnement — une seule variable contrôle la base en dev comme en prod. En local on pointe sur un PostgreSQL installé sur la machine, sur Render on branche le service PostgreSQL managé.

**Tech Stack:** PostgreSQL 16, psycopg2-binary, dj-database-url, Django 6.0

---

## Fichiers concernés

| Action | Fichier | Rôle |
|--------|---------|------|
| Modifier | `requirements.txt` | Remplacer `mysqlclient` par `psycopg2-binary` + `dj-database-url` |
| Modifier | `main/settings.py` | Lire `DATABASE_URL` via `dj_database_url.config()` |
| Modifier | `.env` | Ajouter `DATABASE_URL` local |

---

## Task 1 — Mettre à jour les dépendances

**Fichiers :**
- Modifier : `requirements.txt`

- [ ] **Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/requirements.txt"
```

- [ ] **Remplacer `mysqlclient` par les deux nouvelles dépendances**

Dans `requirements.txt` :
- Supprimer la ligne `mysqlclient==2.2.7`
- Ajouter à la place :

```
psycopg2-binary==2.9.10
dj-database-url==2.3.0
```

- [ ] **Installer les nouvelles dépendances**

```bash
cd "/home/jey/Documents/projet /OpendFood" && pip install psycopg2-binary==2.9.10 dj-database-url==2.3.0
```

Résultat attendu : `Successfully installed psycopg2-binary-2.9.10 dj-database-url-2.3.0`

- [ ] **Vérifier que psycopg2 fonctionne**

```bash
python -c "import psycopg2; print(psycopg2.__version__)"
```

Résultat attendu : `2.9.10 (dt dec pq3 ext lo64)`

- [ ] **Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add requirements.txt && git commit -m "chore: replace mysqlclient with psycopg2-binary and dj-database-url"
```

---

## Task 2 — Mettre à jour settings.py

**Fichiers :**
- Modifier : `main/settings.py`

- [ ] **Lire la section DATABASES actuelle**

```bash
grep -n "DATABASES\|sqlite\|ENGINE" "/home/jey/Documents/projet /OpendFood/main/settings.py"
```

- [ ] **Ajouter l'import dj_database_url en haut du fichier**

Juste après `import os`, ajouter :

```python
import dj_database_url
```

- [ ] **Remplacer le bloc DATABASES**

Remplacer :

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

Par :

```python
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

Cela signifie :
- Si `DATABASE_URL` est défini dans l'environnement → PostgreSQL (ou n'importe quelle URL)
- Sinon → SQLite local (comportement actuel conservé)

- [ ] **Vérifier que Django démarre sans erreur**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check
```

Résultat attendu : `System check identified no issues (0 silenced).`

- [ ] **Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add main/settings.py && git commit -m "feat: read database config from DATABASE_URL env variable"
```

---

## Task 3 — Créer la base PostgreSQL locale et migrer

**Prérequis :** PostgreSQL 16 est déjà installé sur la machine (`psql --version` retourne `16.x`).

- [ ] **Créer la base de données locale**

```bash
createdb openfood_dev
```

Si cette commande échoue avec "role does not exist", lancer d'abord :

```bash
sudo -u postgres createuser --superuser $USER
createdb openfood_dev
```

- [ ] **Vérifier que la base existe**

```bash
psql -l | grep openfood_dev
```

Résultat attendu : une ligne contenant `openfood_dev`.

- [ ] **Ajouter DATABASE_URL dans .env**

Ouvrir `.env` et ajouter à la fin :

```
DATABASE_URL=postgres://localhost/openfood_dev
```

(Si le user PostgreSQL local a un mot de passe, utiliser : `postgres://USER:PASSWORD@localhost/openfood_dev`)

- [ ] **Vérifier que Django lit bien la nouvelle base**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py dbshell -- -c "\conninfo"
```

Résultat attendu : `You are connected to database "openfood_dev" ...`

- [ ] **Appliquer toutes les migrations sur PostgreSQL**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py migrate
```

Résultat attendu : toutes les migrations marquées `OK`, aucune erreur.

- [ ] **Créer un superuser de test**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py createsuperuser
```

- [ ] **Lancer le serveur et vérifier que tout fonctionne**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py runserver
```

Ouvrir `http://localhost:8000/admin/` → connexion avec le superuser créé. Si la page s'affiche → OK.

- [ ] **Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add .env && git commit -m "chore: configure local PostgreSQL database URL"
```

> **Note :** `.env` est dans `.gitignore` (vérifié). Si ce n'est pas le cas, ajouter `.env` au `.gitignore` avant de committer.

---

## Task 4 — Configurer PostgreSQL sur Render

Cette tâche se fait entièrement dans le dashboard Render et ne modifie pas de fichier de code.

- [ ] **Créer le service PostgreSQL sur Render**

  1. Aller sur [dashboard.render.com](https://dashboard.render.com)
  2. Cliquer **New +** → **PostgreSQL**
  3. Nom : `openfood-db`
  4. Plan : **Free** (suffisant pour démarrer)
  5. Cliquer **Create Database**
  6. Attendre ~1 min que le service soit `Available`

- [ ] **Copier l'Internal Database URL**

  Sur la page du service PostgreSQL Render → section **Connections** → copier la valeur de **Internal Database URL** (format `postgres://user:pass@host/dbname`).

  > Utiliser l'**Internal URL** (pas l'External) pour les connexions depuis le Web Service — plus rapide, pas de quota réseau.

- [ ] **Ajouter la variable d'environnement sur le Web Service**

  1. Aller sur le service web `openfood2-0` dans Render
  2. Onglet **Environment**
  3. Ajouter : `DATABASE_URL` = *(la valeur copiée ci-dessus)*
  4. Cliquer **Save Changes** → Render redéploie automatiquement

- [ ] **Vérifier le déploiement**

  Dans les logs Render du déploiement, chercher :

  ```
  Running migrations...
  ```

  Si les migrations ne tournent pas automatiquement, ajouter une **Pre-Deploy Command** dans Render :

  ```
  python manage.py migrate
  ```

  (Settings du Web Service → **Pre-Deploy Command**)

- [ ] **Tester la production**

  Ouvrir `https://openfood2-0.onrender.com/admin/` → si la page s'affiche, la connexion PostgreSQL fonctionne.

---

## Notes importantes

### Subdomain routing en production
`ALLOWED_HOSTS` dans `settings.py` contient `.onrender.com` (avec le point = wildcard subdomain). C'est déjà correct pour les sous-domaines restaurant en prod.

### Pas de transfert de données
On est en dev → SQLite contient uniquement des données de test. Aucun outil de migration de données (pgloader, etc.) n'est nécessaire. On repart d'une base vide et on recrée les données via le panel admin.

### En cas d'erreur `SSL SYSCALL EOF`
Ajouter `?sslmode=require` à la fin de l'Internal Database URL de Render :
```
postgres://user:pass@host/dbname?sslmode=require
```
