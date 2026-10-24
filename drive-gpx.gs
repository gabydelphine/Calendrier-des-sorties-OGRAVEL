/**
 * ÔGravel – dossier GPX sur Google Drive.
 *
 * 1. majDossiers() : crée un dossier « AAAA-MM-JJ Nom de la sortie » pour chaque
 *    sortie du calendrier ÔGravel, et rend les fichiers GPX lisibles par lien.
 *    À lancer automatiquement chaque jour (déclencheur horaire).
 * 2. doGet() : publié en « application Web », donne au robot de l'appli la liste
 *    des sorties et de leurs fichiers GPX.
 */
const DOSSIER_GPX = '1x6wS5I_FBMH_Evxf-Qpqfl_JVkiXrvr0';   // le dossier « gpx » du Drive
const SITE = 'https://gabydelphine.github.io/Calendrier-des-sorties-OGRAVEL/';

function lireJson_(adresse) {
  try {
    const r = UrlFetchApp.fetch(adresse + '?v=' + Date.now(), {muteHttpExceptions: true});
    return r.getResponseCode() === 200 ? JSON.parse(r.getContentText()) : {};
  } catch (e) { return {}; }
}

function sortiesDuCalendrier_() {
  const liste = {};
  const ajouter = (date, titre) => {
    if (!date || !titre || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return;
    if (!liste[date]) liste[date] = titre.replace(/[\/\\]+/g, '-').replace(/\s+/g, ' ').trim();
  };
  (lireJson_(SITE + 'events.json').events || []).forEach(e => ajouter(e.date, e.title));
  (lireJson_(SITE + 'sorties-historique.json').sorties || []).forEach(e => ajouter(e.date, e.title));
  (lireJson_(SITE + 'helloasso.json').evenements || []).forEach(e => ajouter(e.date, e.titre));
  return liste;
}

function majDossiers() {
  const racine = DriveApp.getFolderById(DOSSIER_GPX);
  const existants = {};
  const it = racine.getFolders();
  while (it.hasNext()) {
    const d = it.next(), m = d.getName().match(/^(\d{4}-\d{2}-\d{2})\b/);
    if (m) existants[m[1]] = d;
  }
  const sorties = sortiesDuCalendrier_();
  // Le dossier d'une sortie est créé la veille (jamais plus tôt).
  const demain = Utilities.formatDate(new Date(Date.now() + 864e5), 'Europe/Paris', 'yyyy-MM-dd');
  Object.keys(sorties).forEach(date => {
    if (date > demain) return;
    if (!existants[date]) {
      existants[date] = racine.createFolder(date + ' ' + sorties[date]);
      Logger.log('Dossier créé : ' + date + ' ' + sorties[date]);
    }
  });
  // Les GPX deviennent lisibles par lien, pour que les membres puissent les télécharger.
  Object.keys(existants).forEach(date => {
    const f = existants[date].getFiles();
    while (f.hasNext()) {
      const fichier = f.next();
      if (!/\.gpx$/i.test(fichier.getName())) continue;
      if (fichier.getSharingAccess() !== DriveApp.Access.ANYONE_WITH_LINK) {
        fichier.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
      }
    }
  });
}

function doGet() {
  const racine = DriveApp.getFolderById(DOSSIER_GPX);
  const resultat = [];
  const it = racine.getFolders();
  while (it.hasNext()) {
    const d = it.next(), m = d.getName().match(/^(\d{4}-\d{2}-\d{2})\s+(.+)$/);
    if (!m) continue;
    const gpx = [];
    const f = d.getFiles();
    while (f.hasNext()) {
      const fichier = f.next();
      if (!/\.gpx$/i.test(fichier.getName())) continue;
      // Un GPX tout juste déposé devient lisible par lien tout de suite.
      if (fichier.getSharingAccess() !== DriveApp.Access.ANYONE_WITH_LINK) {
        fichier.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
      }
      gpx.push({id: fichier.getId(), nom: fichier.getName(), taille: fichier.getSize(),
                modifie: fichier.getLastUpdated().toISOString(),
                public: fichier.getSharingAccess() === DriveApp.Access.ANYONE_WITH_LINK});
    }
    resultat.push({date: m[1], nom: m[2], dossier: d.getId(), gpx: gpx});
  }
  resultat.sort((a, b) => b.date.localeCompare(a.date));
  return ContentService.createTextOutput(JSON.stringify({maj: new Date().toISOString(), sorties: resultat}))
    .setMimeType(ContentService.MimeType.JSON);
}

// Le déclencheur quotidien appelle myFunction : elle lance la mise à jour des dossiers.
function myFunction() { majDossiers(); }
