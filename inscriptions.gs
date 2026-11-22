/**
 * ÔGravel – demandes d'inscription aux sorties (compte ogravelinscription@gmail.com).
 *
 * 1. doGet()  : liste publique des demandes (nombre, prénom et nom) par sortie à venir.
 * 2. doPost() : demande ou désinscription envoyée depuis l'appli.
 * 3. lireMails() : lit les mails types (« Inscription ÔGravel JJ/MM/AAAA ») reçus sur
 *    la boîte du club. À lancer toutes les 10 minutes (déclencheur horaire).
 *
 * À chaque demande ou désinscription : un e-mail au président, un e-mail de confirmation
 * de DEMANDE au membre (ce n'est pas une inscription : elle est validée par l'envoi des
 * traces par le président).
 * Les demandes sont rangées dans le tableau « Inscriptions ÔGravel » (feuille « Demandes »).
 */
const SITE = 'https://gabydelphine.github.io/Calendrier-des-sorties-OGRAVEL/';
const PRESIDENT = {nom: 'Thierry Schiavi', email: 'thierry.schiavi@aliceadsl.fr'};
const NOM_CLUB = 'ÔGravel';
// Empreinte SHA-256 du code administrateur (le même que dans l'appli).
const CODE_ADMIN = '093cbcc5e317423d1034794a14f940b88a8912725d6f8a7f1867e2c4abc73e62';
const LIBELLE_TRAITE = 'ÔGravel traité';
const COLONNES = ['horodatage', 'date_sortie', 'sortie', 'prenom', 'nom', 'email', 'parcours', 'message',
                  'canal', 'jeton', 'statut', 'maj'];

/* ---------- Tableau ---------- */
function feuille_() {
  const props = PropertiesService.getScriptProperties();
  let id = props.getProperty('TABLEAU');
  let classeur;
  if (id) { try { classeur = SpreadsheetApp.openById(id); } catch (e) { classeur = null; } }
  if (!classeur) {
    classeur = SpreadsheetApp.create('Inscriptions ÔGravel');
    props.setProperty('TABLEAU', classeur.getId());
  }
  let f = classeur.getSheetByName('Demandes');
  if (!f) {
    f = classeur.getSheets()[0];
    f.setName('Demandes');
    f.getRange(1, 1, 1, COLONNES.length).setValues([COLONNES]).setFontWeight('bold');
    f.setFrozenRows(1);
  }
  return f;
}

function lignes_() {
  const f = feuille_();
  const n = f.getLastRow() - 1;
  if (n < 1) return [];
  return f.getRange(2, 1, n, COLONNES.length).getValues().map((v, i) => {
    const o = {ligne: i + 2};
    COLONNES.forEach((c, j) => { o[c] = v[j]; });
    o.date_sortie = texteDate_(o.date_sortie);
    o.email = String(o.email || '').toLowerCase();
    return o;
  });
}

function texteDate_(v) {
  if (v instanceof Date) return Utilities.formatDate(v, 'Europe/Paris', 'yyyy-MM-dd');
  return String(v || '');
}

/** Les demandes annulées (par le membre, ou « desinscrit » écrit à la main) quittent la
 *  feuille « Demandes » pour la feuille « Désinscriptions » : on garde la trace sans encombrer. */
function rangerDesinscrits_() {
  const f = feuille_();
  const n = f.getLastRow() - 1;
  if (n < 1) return;
  const valeurs = f.getRange(2, 1, n, COLONNES.length).getValues();
  const iStatut = COLONNES.indexOf('statut');
  const a_ranger = [];
  valeurs.forEach((v, i) => { if (String(v[iStatut]).trim().toLowerCase().replace('é', 'e') === 'desinscrit') a_ranger.push(i + 2); });
  if (!a_ranger.length) return;
  const classeur = f.getParent();
  let archive = classeur.getSheetByName('Désinscriptions');
  if (!archive) {
    archive = classeur.insertSheet('Désinscriptions');
    archive.getRange(1, 1, 1, COLONNES.length).setValues([COLONNES]).setFontWeight('bold');
    archive.setFrozenRows(1);
  }
  a_ranger.forEach(r => archive.appendRow(valeurs[r - 2]));
  a_ranger.reverse().forEach(r => f.deleteRow(r));
}

/* ---------- Sorties du calendrier ---------- */
function sorties_() {
  const cache = CacheService.getScriptCache();
  const en = cache.get('sorties');
  if (en) return JSON.parse(en);
  const liste = {};
  try {
    const r = UrlFetchApp.fetch(SITE + 'events.json?v=' + Date.now(), {muteHttpExceptions: true});
    if (r.getResponseCode() === 200) {
      (JSON.parse(r.getContentText()).events || []).forEach(e => {
        if (e.date && !liste[e.date]) liste[e.date] = {titre: e.title || 'Sortie ' + NOM_CLUB, lieu: e.location || ''};
      });
    }
  } catch (e) {}
  cache.put('sorties', JSON.stringify(liste), 600);
  return liste;
}

function dateLongue_(iso) {
  const d = new Date(iso + 'T12:00:00');
  const jours = ['dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi'];
  const mois = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
  return jours[d.getDay()] + ' ' + d.getDate() + ' ' + mois[d.getMonth()] + ' ' + d.getFullYear();
}

/* ---------- Liste publique ---------- */
function listePublique_() {
  const auj = Utilities.formatDate(new Date(), 'Europe/Paris', 'yyyy-MM-dd');
  const res = {};
  lignes_().forEach(l => {
    if (l.statut !== 'demande' || l.date_sortie < auj) return;
    (res[l.date_sortie] = res[l.date_sortie] || []).push({prenom: l.prenom, nom: l.nom, canal: l.canal});
  });
  return res;
}

function reponse_(objet) {
  return ContentService.createTextOutput(JSON.stringify(objet)).setMimeType(ContentService.MimeType.JSON);
}

function doGet() {
  return reponse_({maj: new Date().toISOString(), inscrits: listePublique_()});
}

/* ---------- Demandes ---------- */
function propre_(t, max) {
  return String(t || '').replace(/[\u0000-\u001f<>]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max || 80);
}
function emailValide_(e) { return /^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$/i.test(e); }
function empreinte_(texte) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, texte, Utilities.Charset.UTF_8)
    .map(b => ((b + 256) % 256).toString(16).padStart(2, '0')).join('');
}

/** Enregistre une demande. Renvoie {ok, deja?, erreur?}. */
function demander_(d) {
  const sortie = sorties_()[d.date];
  if (!sortie) return {ok: false, erreur: "pas de sortie ÔGravel le " + d.date};
  const auj = Utilities.formatDate(new Date(), 'Europe/Paris', 'yyyy-MM-dd');
  if (d.date < auj) return {ok: false, erreur: 'cette sortie est passée'};
  const f = feuille_();
  const existante = lignes_().find(l => l.date_sortie === d.date && l.email === d.email && l.statut === 'demande');
  if (existante) {
    // Déjà demandée : on rattache simplement ce téléphone, sans renvoyer de mails.
    if (d.jeton && !existante.jeton) f.getRange(existante.ligne, COLONNES.indexOf('jeton') + 1).setValue(d.jeton);
    return {ok: true, deja: true};
  }
  const maintenant = new Date();
  f.appendRow([maintenant, d.date, sortie.titre, d.prenom, d.nom, d.email, d.parcours || '', d.message || '',
               d.canal, d.jeton || '', 'demande', maintenant]);
  mailPresident_('demande', d, sortie);
  mailMembre_('demande', d, sortie);
  return {ok: true};
}

/** Annule une demande. qui = {jeton} (appli), {email} (mail) ou {admin: true}. */
function annuler_(date, email, qui) {
  const l = lignes_().find(x => x.date_sortie === date && x.email === email && x.statut === 'demande');
  if (!l) return {ok: false, erreur: 'aucune demande trouvée'};
  const autorise = qui.admin || (qui.jeton && l.jeton && qui.jeton === l.jeton) || (qui.email && qui.email === l.email);
  if (!autorise) return {ok: false, erreur: 'désinscription possible seulement depuis le téléphone utilisé pour la demande'};
  const f = feuille_();
  f.getRange(l.ligne, COLONNES.indexOf('statut') + 1, 1, 2).setValues([['desinscrit', new Date()]]);
  rangerDesinscrits_();
  const sortie = sorties_()[date] || {titre: l.sortie, lieu: ''};
  const d = {date: date, prenom: l.prenom, nom: l.nom, email: l.email, parcours: l.parcours, canal: qui.canal || l.canal};
  mailPresident_('desinscription', d, sortie);
  if (!qui.admin) mailMembre_('desinscription', d, sortie);
  return {ok: true};
}

function doPost(e) {
  let d;
  try { d = JSON.parse(e.postData.contents); } catch (err) { return reponse_({ok: false, erreur: 'requête illisible'}); }
  const verrou = LockService.getScriptLock();
  verrou.waitLock(20000);
  try {
    const date = String(d.date || '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return reponse_({ok: false, erreur: 'date de sortie manquante'});
    const email = propre_(d.email, 120).toLowerCase();
    let r;
    if (d.action === 'inscrire') {
      const prenom = propre_(d.prenom, 50), nom = propre_(d.nom, 50);
      if (!prenom || !nom) return reponse_({ok: false, erreur: 'prénom et nom obligatoires'});
      if (!emailValide_(email)) return reponse_({ok: false, erreur: 'adresse e-mail invalide'});
      r = demander_({date: date, prenom: prenom, nom: nom, email: email, parcours: propre_(d.parcours, 80),
                     message: propre_(d.message, 1000), canal: 'appli', jeton: propre_(d.jeton, 64)});
    } else if (d.action === 'desinscrire') {
      const admin = d.code && empreinte_(String(d.code).trim().toLowerCase()) === CODE_ADMIN;
      r = annuler_(date, email, {jeton: propre_(d.jeton, 64), admin: admin, canal: 'appli'});
    } else {
      return reponse_({ok: false, erreur: 'action inconnue'});
    }
    r.inscrits = listePublique_()[date] || [];
    return reponse_(r);
  } finally {
    verrou.releaseLock();
  }
}

/* ---------- Mails ---------- */
function mailPresident_(type, d, sortie) {
  const titre = sortie.titre + ' du ' + dateLongue_(d.date);
  const quoi = type === 'demande' ? 'Demande d\'inscription' : 'Désinscription';
  const corps = [
    'Bonjour ' + PRESIDENT.nom.split(' ')[0] + ',', '',
    quoi + (d.canal === 'mail' ? ' reçue par e-mail' : ' faite dans l\'appli') + ' :', '',
    'Sortie : ' + titre,
    'Participant : ' + d.prenom + ' ' + d.nom,
    'E-mail : ' + d.email,
    d.parcours ? 'Parcours : ' + d.parcours : null,
    d.message ? '\nMessage : ' + d.message : null,
    '', 'Nombre de demandes pour cette sortie : ' + ((listePublique_()[d.date] || []).length),
    '', '— Message automatique ' + NOM_CLUB,
  ].filter(x => x !== null).join('\n');
  MailApp.sendEmail({to: PRESIDENT.email, replyTo: d.email, name: NOM_CLUB + ' inscriptions',
                     subject: NOM_CLUB + ' – ' + quoi + ' – ' + d.prenom + ' ' + d.nom + ' – ' + titre, body: corps});
}

function mailMembre_(type, d, sortie) {
  const titre = '« ' + sortie.titre + ' » du ' + dateLongue_(d.date);
  const lignes = type === 'demande' ? [
    'Bonjour ' + d.prenom + ',', '',
    'Nous avons bien reçu ta DEMANDE d\'inscription à la sortie ' + NOM_CLUB + ' ' + titre + '.', '',
    '⚠️ Ce message confirme seulement la réception de ta demande : ce n\'est pas une inscription.',
    'Ton inscription sera validée quand le président t\'enverra les traces de la sortie.',
    'Si tu ne reçois pas les traces, rapproche-toi du président, ' + PRESIDENT.nom + ' (il suffit de répondre à ce message).', '',
    'Pour annuler ta demande : bouton « Me désinscrire » dans l\'appli, ou e-mail à cette adresse avec l\'objet',
    '« Désinscription ' + NOM_CLUB + ' ' + d.date.split('-').reverse().join('/') + ' ».', '',
    'Sportivement,', NOM_CLUB,
  ] : [
    'Bonjour ' + d.prenom + ',', '',
    'Ta demande d\'inscription à la sortie ' + NOM_CLUB + ' ' + titre + ' est annulée. Le président est prévenu.', '',
    'Sportivement,', NOM_CLUB,
  ];
  MailApp.sendEmail({to: d.email, replyTo: PRESIDENT.email, name: NOM_CLUB,
                     subject: NOM_CLUB + ' – ' + (type === 'demande' ? 'Demande d\'inscription bien reçue' : 'Désinscription prise en compte') + ' – ' + titre.replace(/[«»]/g, '').trim(),
                     body: lignes.join('\n')});
}

/* ---------- Mails types reçus sur la boîte du club ---------- */
function champ_(texte, nom) {
  const m = texte.match(new RegExp('^\\s*\\*?' + nom + '\\*?\\s*:\\s*(.+)$', 'im'));
  return m ? m[1].trim() : '';
}

function lireMails() {
  const libelle = GmailApp.getUserLabelByName(LIBELLE_TRAITE) || GmailApp.createLabel(LIBELLE_TRAITE);
  rangerDesinscrits_();
  const fils = GmailApp.search('in:inbox subject:(inscription OR désinscription OR desinscription) newer_than:7d', 0, 50);
  if (!fils.length) return;
  const verrou = LockService.getScriptLock();
  verrou.waitLock(30000);
  try {
    // Les messages déjà lus sont notés dans la feuille « Mails » (un fil peut recevoir une réponse plus tard).
    const classeur = feuille_().getParent();
    const journal = classeur.getSheetByName('Mails') || classeur.insertSheet('Mails');
    const vus = new Set(journal.getLastRow() ? journal.getRange(1, 1, journal.getLastRow(), 1).getValues().map(v => String(v[0])) : []);
    const moi = Session.getEffectiveUser().getEmail().toLowerCase();
    fils.forEach(fil => {
      fil.getMessages().forEach(msg => {
        if (vus.has(msg.getId()) || msg.getFrom().toLowerCase().indexOf(moi) >= 0) return;
        try { traiterMail_(msg); } catch (err) { Logger.log('Mail ' + msg.getId() + ' : ' + err); }
        journal.appendRow([msg.getId(), new Date(), msg.getFrom(), msg.getSubject()]);
        vus.add(msg.getId());
      });
      fil.addLabel(libelle);
    });
  } finally {
    verrou.releaseLock();
  }
}

function traiterMail_(msg) {
  const sujet = msg.getSubject() || '';
  const sujetSimple = sujet.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  if (!/gravel/.test(sujetSimple)) return;
  const desinscription = /desinscri/.test(sujetSimple);
  const expediteur = msg.getFrom();
  const email = ((expediteur.match(/<([^>]+)>/) || [])[1] || expediteur).trim().toLowerCase();
  const nomAffiche = (expediteur.replace(/<[^>]*>/, '').replace(/"/g, '').trim());
  const corps = msg.getPlainBody() || '';
  const m = sujet.match(/(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{2,4})/) || corps.match(/date\s*:\s*(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{2,4})/i);
  if (!m || !emailValide_(email)) return incompris_(msg, email, 'la date de la sortie (JJ/MM/AAAA) est absente de l\'objet');
  const annee = m[3].length === 2 ? '20' + m[3] : m[3];
  const date = annee + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[1]).slice(-2);
  if (desinscription) {
    const r = annuler_(date, email, {email: email, canal: 'mail'});
    if (!r.ok) incompris_(msg, email, 'aucune demande à ton adresse pour la sortie du ' + m[0]);
    return;
  }
  let prenom = propre_(champ_(corps, 'pr[ée]nom'), 50), nom = propre_(champ_(corps, 'nom'), 50);
  if (!prenom && !nom && nomAffiche) { const p = nomAffiche.split(/\s+/); prenom = p.shift(); nom = p.join(' '); }
  if (!prenom || !nom) return incompris_(msg, email, 'il manque ton prénom ou ton nom');
  const r = demander_({date: date, prenom: prenom, nom: nom, email: email, parcours: propre_(champ_(corps, 'parcours'), 80),
                       message: propre_(champ_(corps, 'message'), 1000), canal: 'mail'});
  if (!r.ok) incompris_(msg, email, r.erreur);
}

function incompris_(msg, email, raison) {
  if (!emailValide_(email)) return;
  MailApp.sendEmail({to: email, replyTo: PRESIDENT.email, name: NOM_CLUB,
    subject: NOM_CLUB + ' – Demande non prise en compte : ' + (msg.getSubject() || ''),
    body: ['Bonjour,', '', 'Nous n\'avons pas pu prendre en compte ton message (' + raison + ').', '',
           'Merci de renvoyer le mail type :', '',
           'Objet : Inscription ' + NOM_CLUB + ' JJ/MM/AAAA   (la date de la sortie)',
           'Nom : …', 'Prénom : …', 'Parcours : …', '',
           'Pour annuler : même mail avec l\'objet « Désinscription ' + NOM_CLUB + ' JJ/MM/AAAA ».', '',
           'Pour toute question, réponds à ce message : il arrivera chez le président.', '', NOM_CLUB].join('\n')});
}

/** À lancer une fois à la main : crée le tableau et le déclencheur des mails. */
function installer() {
  feuille_();
  rangerDesinscrits_();
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'lireMails').forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('lireMails').timeBased().everyMinutes(10).create();
  Logger.log('Tableau : ' + SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('TABLEAU')).getUrl());
}
