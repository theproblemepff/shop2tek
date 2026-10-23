# Bot Discord tout-en-un + panel (phases 1-2)

## Pages du panel
Démarrer (checklist automatique), Tableau de bord (stats réelles, graphique 7 jours), Configuration (listes de salons/rôles du serveur, aide sur chaque champ), Commandes (toutes les commandes expliquées), Modération (historique filtrable), Membres (recherche), Logs (filtres, erreurs).

## Lancement
1. `start.sh` (Linux) ou `start.bat` (Windows) : crée l'environnement, installe les dépendances, génère `.env`.
2. Renseigne `.env` (token, mot de passe du panel, secret de session) puis relance.
3. Panel : http://127.0.0.1:8000

## Portail développeur Discord
Active les intents **Server Members** et **Message Content**. Invite le bot avec les scopes `bot` et `applications.commands`.

## Tests
`pytest`

## État
Fait : vérification (bouton / règlement / question, anti double-clic, expiration configurable), modération (warn, warnings, timeout, untimeout, kick, ban, unban, purge, slowmode, lock, unlock, history, modlogs), configuration persistante en base, bot + panel dans un seul processus, authentification du panel (mot de passe, limitation des tentatives), accueil/départ, API de config, tests.
À faire : anti-spam, anti-liens, tickets, /modele, logs, sauvegardes, automatisations, interface complète du panel, OAuth2 Discord.

## Permissions du bot
Gérer les rôles, expulser, bannir, exclure des membres, gérer les messages et les salons. Le rôle du bot doit être placé au-dessus des rôles à gérer.

## Vérification
Configure `roles.member`, `roles.unverified`, `channels.verification` et `verification.enabled` via `PUT /api/config/{section}`, puis lance `/verification-publier`. Un simple bouton ne prouve pas qu'on est humain : il filtre seulement les comptes les plus basiques. Le mode question est un peu plus robuste mais reste contournable.

## Hébergement
Voir `DEPLOIEMENT_REPLIT.md`. En local, SQLite suffit. Pour un hébergement sans disque persistant, renseigne `DATABASE_URL` avec une base PostgreSQL.
