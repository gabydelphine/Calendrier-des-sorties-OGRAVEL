ÔGRAVEL — SYNTHÈSE DES PROCHAINES SORTIES

Page publique : https://gabydelphine.github.io/Calendrier-des-sorties-OGRAVEL/
Abonnement agenda (téléphone, Google Agenda, Outlook) :
  https://gabydelphine.github.io/Calendrier-des-sorties-OGRAVEL/ogravel.ics

D'OÙ VIENNENT LES DATES
Le robot lit le calendrier officiel https://ogravel.com/calendrier/
(rubrique « Les RDV des membres » + les « Surprise ride » datées),
sans accès à l'administration du site ÔGravel.

FONCTIONNEMENT
- Tous les jours à 05:15 UTC (workflow « Actualiser le calendrier ÔGravel ») :
  update.py écrit events.json, puis generer_ics.py écrit ogravel.ics.
- Seules les sorties à venir sont gardées.
- Année manquante : le calendrier étant chronologique, une date dont le mois
  recule (décembre → janvier) passe à l'année suivante.
- Les sorties sur plusieurs jours apparaissent sur toute leur durée dans l'agenda.
- En cas d'échec (site indisponible, structure modifiée), la dernière liste
  valide reste publiée. GitHub envoie alors un e-mail d'échec du workflow.

À SURVEILLER
- Si ogravel.com change la présentation de sa page, adapter update.py.
- Le bouton « Je souhaite participer » prépare un e-mail à l'adresse inscrite
  dans index.html.
