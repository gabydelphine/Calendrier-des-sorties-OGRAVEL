/**
 * ÔGravel – dossier GPX sur Google Drive.
 *
 * 1. majDossiers() : crée un dossier « AAAA-MM-JJ Nom de la sortie » pour chaque
 *    sortie du calendrier ÔGravel, et rend les fichiers GPX lisibles par lien.
 *    À lancer automatiquement chaque jour (déclencheur horaire).
 * 2. doGet() : publié en « application Web », donne au robot de l'appli la liste
 *    des sorties et de leurs fichiers GPX.
 * 3. doPost() : reçoit une trace GPX envoyée depuis l'appli en mode administrateur
 *    (protégé par le code) et la range dans le dossier de la sortie.
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

// Empreinte SHA-256 du code administrateur (le même que dans l'appli).
const CODE_ADMIN = '093cbcc5e317423d1034794a14f940b88a8912725d6f8a7f1867e2c4abc73e62';

function empreinte_(texte) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, texte, Utilities.Charset.UTF_8)
    .map(b => ((b + 256) % 256).toString(16).padStart(2, '0')).join('');
}

function reponse_(objet) {
  return ContentService.createTextOutput(JSON.stringify(objet)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  let d;
  try { d = JSON.parse(e.postData.contents); } catch (err) { return reponse_({ok: false, erreur: 'requête illisible'}); }
  if (d.action !== 'ajouter_trace') return reponse_({ok: false, erreur: 'action inconnue'});
  if (empreinte_(String(d.code || '').trim().toLowerCase()) !== CODE_ADMIN) return reponse_({ok: false, erreur: 'code incorrect'});
  const date = String(d.date || '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return reponse_({ok: false, erreur: 'date de sortie manquante'});
  const contenu = String(d.contenu || '');
  if (!/<gpx[\s>]/i.test(contenu)) return reponse_({ok: false, erreur: "ce n'est pas un GPX"});
  if (contenu.length > 15e6) return reponse_({ok: false, erreur: 'fichier trop gros'});
  let nom = String(d.nom || 'trace.gpx').replace(/[\/\\:*?"<>|]+/g, '-').replace(/\s+/g, ' ').trim().slice(0, 120);
  if (!/\.gpx$/i.test(nom)) nom += '.gpx';

  const verrou = LockService.getScriptLock();
  verrou.waitLock(20000);
  try {
    const racine = DriveApp.getFolderById(DOSSIER_GPX);
    let dossier = null;
    const it = racine.getFolders();
    while (it.hasNext() && !dossier) { const x = it.next(); if (x.getName().indexOf(date + ' ') === 0 || x.getName() === date) dossier = x; }
    if (!dossier) {
      let titre = String(d.titre || '').replace(/[\/\\]+/g, '-').replace(/\s+/g, ' ').trim();
      if (!titre) titre = sortiesDuCalendrier_()[date] || 'Sortie ÔGravel';
      dossier = racine.createFolder(date + ' ' + titre.slice(0, 100));
    }
    // Même nom déjà présent : on remplace l'ancienne version (elle part à la corbeille du Drive).
    const memes = dossier.getFilesByName(nom);
    while (memes.hasNext()) memes.next().setTrashed(true);
    const fichier = dossier.createFile(nom, contenu, 'application/gpx+xml');
    fichier.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    return reponse_({ok: true, dossier: dossier.getName(), fichier: nom});
  } finally {
    verrou.releaseLock();
  }
}

// Le déclencheur quotidien appelle myFunction : elle lance la mise à jour des dossiers.
function myFunction() { majDossiers(); }
