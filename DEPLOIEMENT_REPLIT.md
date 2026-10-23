# Héberger sur Replit

## À savoir avant de commencer
- Il faut un déploiement de type **Reserved VM** : c'est le seul qui garde le bot connecté en permanence.
- Le disque d'un déploiement Replit est **effacé à chaque nouvelle publication**. La base SQLite et le fichier `exports/` seraient perdus.
  Le projet utilise donc une base **PostgreSQL** (Replit en propose une dans l'outil « Database »).
  Le fichier TXT sur disque n'est qu'une copie temporaire : télécharge toujours tes ID depuis l'onglet **ID** du panel.
- Ne lance JAMAIS le bot en même temps dans l'éditeur (bouton Run) et dans le déploiement : il répondrait deux fois.

## Étapes
1. Crée un Repl Python, puis importe tout le contenu du zip à la racine.
2. Outil **Database** : crée la base PostgreSQL. Replit définit alors lui-même la variable `DATABASE_URL`.
3. Outil **Secrets** : ajoute `DISCORD_TOKEN`, `PANEL_ADMIN_PASSWORD` (20 caractères ou plus) et `PANEL_SECRET` (suite aléatoire longue).
   Pense à les ajouter aussi dans les secrets du déploiement s'ils ne s'y copient pas.
4. Test : bouton Run. Tu dois voir « Connecté en tant que… » dans la console. Arrête-le ensuite.
5. Outil **Deployments** : choisis **Reserved VM**, la plus petite taille, build `pip install -r requirements.txt`, run `python run.py`, puis publie.
6. Le panel est à l'adresse `https://ton-app.replit.app`.

## Si le panel te bloque
5 mauvais mots de passe bloquent les connexions pendant 5 minutes. Sur Replit, cette limite peut s'appliquer à tout le monde à la fois : attends simplement 5 minutes.
