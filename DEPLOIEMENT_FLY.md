# Déploiement sur Fly.io

1. Installe flyctl (PowerShell) : `iwr https://fly.io/install.ps1 -useb | iex`, puis `fly auth signup` (ou `fly auth login`).
2. Ouvre `fly.toml` et remplace `CHANGE-MOI-nom-unique` par un nom unique.
3. Dans le dossier du projet : `fly launch --no-deploy --copy-config`
   (réponds NON si on te propose une base de données, NON au déploiement immédiat).
4. Volume (stocke la base, les exports et les logs) : `fly volumes create botdata --size 1 --region cdg`
5. Secrets (ne les écris jamais dans un fichier du projet) :
   `fly secrets set DISCORD_TOKEN=... PANEL_ADMIN_PASSWORD=... PANEL_SECRET=...`
   PANEL_ADMIN_PASSWORD : 20 caractères ou plus. PANEL_SECRET : `python -c "import secrets; print(secrets.token_urlsafe(48))"`
6. Déploiement sur UNE seule machine : `fly deploy --ha=false`
7. Vérifie : `fly status` puis `fly logs`. Le panel est sur `https://TON-NOM.fly.dev`.

Mises à jour : relance `fly deploy --ha=false`. Le volume conserve la base SQLite et le fichier TXT des ID.
Garde une seule machine : la base SQLite est sur le volume d'une seule machine.
