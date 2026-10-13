ÔGRAVEL — SYNTHÈSE DES PROCHAINES SORTIES

Cette page récupère les rendez-vous du calendrier officiel https://ogravel.com/calendrier/
Sans accès à l'administration du site ÔGravel.

MISE EN LIGNE (une seule fois)
1. Créer un compte GitHub gratuit si nécessaire.
2. Créer un dépôt PUBLIC nommé « ogravel-sorties ».
3. Y déposer index.html, update.py, et le dossier .github/workflows/update.yml
   (respecter le dossier caché .github et son arborescence).
4. Dans le dépôt, ouvrir Actions > « Actualiser le calendrier ÔGravel » > Run workflow.
5. Vérifier qu'un fichier events.json a été créé.
6. Dans Settings > Pages, sélectionner « Deploy from a branch », branche main, dossier /(root).
7. Après publication, la page sera à une adresse du type
   https://VOTRE-IDENTIFIANT.github.io/ogravel-sorties/
8. Copier cette adresse dans les Annonces WhatsApp et épingler le message.

MISE À JOUR
Le robot tente une actualisation tous les jours à 05:15 UTC.
En cas d'échec, la dernière liste valide reste publiée.
Le calendrier officiel peut changer de structure : dans ce cas, adapter update.py.
Les événements dont l'année n'est pas précisée sont interprétés comme étant de l'année courante.
Les dates sur plusieurs jours sont affichées par leur premier jour.
GitHub peut désactiver les tâches planifiées d'un dépôt public inactif : vérifier périodiquement l'onglet Actions.

IMPORTANT
La page n'est PAS encore en ligne. Un compte GitHub et la publication initiale sont nécessaires.
La lecture automatique du site doit être testée une fois en ligne.
