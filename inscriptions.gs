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
// Adresse publique de ce programme (application Web) : lien « Annuler ma demande » des e-mails.
const URL_APPLI = 'https://script.google.com/macros/s/AKfycbxLwAzupua7Nw7krKiZbjYSJ7uqyxjmvJeZUa0ZHmWecsFhDxakuOKB2a8VU43E2MI/exec';
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
        if (e.date && !liste[e.date]) liste[e.date] = {titre: e.title || 'Sortie ' + NOM_CLUB, lieu: e.location || '',
                                                       parcours: (e.parcours || []).filter(c => c.libelle)};
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
  // Le président, organisateur, est toujours présent : il figure en tête de chaque sortie à venir.
  const [prenomP, ...nomP] = PRESIDENT.nom.split(' ');
  Object.keys(sorties_()).filter(d => d >= auj).forEach(d => {
    const liste = (res[d] || []).filter(x => simple_(x.prenom + ' ' + x.nom) !== simple_(PRESIDENT.nom));
    res[d] = [{prenom: prenomP, nom: nomP.join(' '), canal: 'organisateur'}].concat(liste);
  });
  return res;
}

function reponse_(objet) {
  return ContentService.createTextOutput(JSON.stringify(objet)).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.annuler) return pageAnnulation_(String(p.annuler), p.ok === '1');
  return reponse_({maj: new Date().toISOString(), inscrits: listePublique_()});
}

/* ---------- Clés : la colonne « jeton » contient la clé du lien e-mail puis celles des appareils ---------- */
function nouveauSecret_() { return Utilities.getUuid().replace(/-/g, ''); }
function jetons_(l) { return String(l.jeton || '').split(',').map(x => x.trim()).filter(Boolean); }
/** Clé du lien « Annuler ma demande » d'une ligne (créée si besoin, pour les lignes anciennes ou saisies à la main). */
function secretDe_(l) {
  const j = jetons_(l);
  if (j.length) return j[0];
  const s = nouveauSecret_();
  feuille_().getRange(l.ligne, COLONNES.indexOf('jeton') + 1).setValue(s);
  return s;
}
function lienAnnulation_(secret) { return URL_APPLI + '?annuler=' + secret; }

function page_(titre, texte, bouton) {
  const h = '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<div style="font-family:system-ui,sans-serif;max-width:480px;margin:40px auto;padding:0 18px;color:#2b2b2b">' +
    '<h2 style="color:#8b2f3c">' + titre + '</h2><p style="font-size:1.05rem;line-height:1.5">' + texte + '</p>' +
    (bouton ? '<p><a href="' + bouton.url + '" target="_top" style="display:inline-block;background:#8b2f3c;color:#fff;padding:12px 20px;border-radius:10px;text-decoration:none;font-weight:600">' + bouton.texte + '</a></p>' : '') +
    '<p style="color:#888;margin-top:30px">' + NOM_CLUB + '</p></div>';
  return HtmlService.createHtmlOutput(h).setTitle(NOM_CLUB + ' – ' + titre).addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
function echapperHtml_(t) { return String(t || '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c])); }

/** Lien « Annuler ma demande » : 1er clic = page de confirmation (les robots anti-spam qui
 *  ouvrent les liens n'annulent donc rien), 2e clic = annulation. */
function pageAnnulation_(secret, confirme) {
  const verrou = LockService.getScriptLock();
  verrou.waitLock(20000);
  try {
    const l = lignes_().find(x => x.statut === 'demande' && jetons_(x).indexOf(secret) >= 0);
    if (!l) return page_('Demande introuvable', 'Cette demande est déjà annulée, ou le lien n\'est plus valable.');
    const quoi = '« ' + echapperHtml_(l.sortie) + ' » du ' + dateLongue_(l.date_sortie);
    if (!confirme) {
      return page_('Annuler ma demande', echapperHtml_(l.prenom + ' ' + l.nom) + ', veux-tu vraiment annuler ta demande d\'inscription à la sortie ' + quoi + ' ?',
                   {url: lienAnnulation_(secret) + '&ok=1', texte: 'Oui, annuler ma demande'});
    }
    annuler_(l.date_sortie, l.email, {jeton: secret, canal: 'lien'});
    return page_('Demande annulée', 'Ta demande pour la sortie ' + quoi + ' est annulée. Le président est prévenu, et un e-mail de confirmation t\'est envoyé.');
  } finally {
    verrou.releaseLock();
  }
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
    // Déjà demandée (autre téléphone, ordinateur…) : on rattache cet appareil, sans renvoyer de mails.
    const j = jetons_(existante);
    if (d.jeton && j.indexOf(d.jeton) < 0) {
      if (!j.length) j.push(nouveauSecret_());
      f.getRange(existante.ligne, COLONNES.indexOf('jeton') + 1).setValue(j.concat(d.jeton).join(','));
    }
    return {ok: true, deja: true};
  }
  const lu = choisirParcours_(d.parcours, sortie.parcours);
  if (lu && lu !== d.parcours) { d.parcoursEcrit = d.parcours; d.parcours = lu; }
  const maintenant = new Date();
  d.secret = nouveauSecret_();
  f.appendRow([maintenant, d.date, sortie.titre, d.prenom, d.nom, d.email, d.parcours || '', d.message || '',
               d.canal, [d.secret, d.jeton].filter(Boolean).join(','), 'demande', maintenant]);
  mailPresident_('demande', d, sortie);
  mailMembre_('demande', d, sortie);
  return {ok: true};
}

/** Annule une demande. qui = {jeton} (appli), {email} (mail) ou {admin: true}. */
function annuler_(date, email, qui) {
  const l = lignes_().find(x => x.date_sortie === date && x.email === email && x.statut === 'demande');
  if (!l) return {ok: false, erreur: 'aucune demande trouvée'};
  const autorise = qui.admin || (qui.jeton && jetons_(l).indexOf(qui.jeton) >= 0) || (qui.email && qui.email === l.email);
  if (!autorise) {
    // Appareil inconnu : on envoie à l'adresse de la demande un lien pour confirmer l'annulation.
    if (qui.envoyerLien) {
      MailApp.sendEmail({to: l.email, replyTo: PRESIDENT.email, name: NOM_CLUB,
        subject: NOM_CLUB + ' – Confirme l\'annulation de ta demande – ' + l.sortie,
        body: ['Bonjour ' + l.prenom + ',', '', 'Pour annuler ta demande d\'inscription à la sortie « ' + l.sortie + ' » du ' + dateLongue_(date) + ', clique ici :',
               lienAnnulation_(secretDe_(l)), '', 'Si tu n\'as rien demandé, ignore simplement ce message.', '', NOM_CLUB].join('\n')});
      return {ok: false, lien: true, erreur: 'un e-mail de confirmation a été envoyé à ' + l.email};
    }
    return {ok: false, erreur: 'désinscription impossible depuis cet appareil'};
  }
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
      r = annuler_(date, email, {jeton: propre_(d.jeton, 64), admin: admin, canal: 'appli', envoyerLien: true});
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
    quoi + (d.canal === 'mail' ? ' reçue par e-mail' : d.canal === 'lien' ? ' faite avec le lien de l\'e-mail de confirmation' : ' faite dans l\'appli') + ' :', '',
    'Sortie : ' + titre,
    'Participant : ' + d.prenom + ' ' + d.nom,
    'E-mail : ' + d.email,
    d.parcours ? 'Parcours : ' + d.parcours + (d.parcoursEcrit ? '   (écrit : « ' + d.parcoursEcrit + ' »)' : '') : null,
    d.message ? '\nMessage : ' + d.message : null,
    d.alerte ? '\n⚠️ ' + d.alerte : null,
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
    'Pour annuler ta demande, depuis n\'importe quel appareil :',
    d.secret ? lienAnnulation_(d.secret) : '(bouton « Me désinscrire » dans l\'appli)',
    'ou e-mail à cette adresse avec l\'objet « Désinscription ' + NOM_CLUB + ' ' + d.date.split('-').reverse().join('/') + ' ».', '',
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
  const fils = GmailApp.search('in:inbox subject:(inscription OR inscriptions OR inscrire OR inscris OR inscrit OR inscrits OR désinscription OR desinscription OR désinscrire OR desinscrire) newer_than:7d', 0, 50);
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
  if (!/inscri/.test(sujetSimple)) return;   // le mot « gravel » n'est plus exigé : l'essentiel est la date
  const desinscription = /desinscri/.test(sujetSimple);
  const expediteur = msg.getFrom();
  const email = ((expediteur.match(/<([^>]+)>/) || [])[1] || expediteur).trim().toLowerCase();
  const nomAffiche = (expediteur.replace(/<[^>]*>/, '').replace(/"/g, '').trim());
  const corps = msg.getPlainBody() || '';
  const lue = dateDuSujet_(sujet) || dateDuSujet_((corps.match(/date\s*:\s*([^\n]+)/i) || [])[1] || '');
  if (!lue || !emailValide_(email)) return incompris_(msg, email, 'la date de la sortie (JJ/MM/AAAA) est absente de l\'objet');
  const date = lue.date, m = [lue.texte];
  // « Inscrits ÔGravel JJ/MM/AAAA » : liste envoyée par le président (ou un administrateur).
  if (/\binscrits\b/.test(sujetSimple)) return listePresident_(msg, email, date, corps);
  if (desinscription) {
    const r = annuler_(date, email, {email: email, canal: 'mail'});
    if (!r.ok) incompris_(msg, email, 'aucune demande à ton adresse pour la sortie du ' + m[0]);
    return;
  }
  let prenom = propre_(champ_(corps, 'pr[ée]nom'), 50), nom = propre_(champ_(corps, 'nom'), 50);
  let parcours = propre_(champ_(corps, 'parcours'), 80), alerte = '';
  // « Nom : Fauvel Maurice » sans ligne « Prénom » : on coupe en deux.
  if (!prenom && nom.indexOf(' ') > 0) { const p = nom.split(' '); nom = p.shift(); prenom = p.join(' '); }
  if (!prenom && !nom) {
    // Mail sans étiquettes, par exemple « Fauvel Maurice Circuit court » : première ligne utile
    // = Nom Prénom (ordre du mail type), puis le parcours.
    const g = lireLigneLibre_(corps, nomAffiche);
    if (g) {
      prenom = g.prenom; nom = g.nom; if (!parcours) parcours = g.parcours;
      alerte = 'Mail hors format, à vérifier : « ' + g.ligne + ' » → ' + prenom + ' ' + nom + (g.parcours ? ', parcours « ' + g.parcours + ' »' : '');
    } else if (nomAffiche && nomAffiche.indexOf('@') < 0) {
      const p = nomAffiche.split(/\s+/); prenom = p.shift(); nom = p.join(' ');
      alerte = 'Mail hors format : nom pris dans l\'expéditeur (« ' + nomAffiche + ' »), à vérifier';
    }
  }
  if (!prenom || !nom) return incompris_(msg, email, 'il manque ton prénom ou ton nom');
  const r = demander_({date: date, prenom: prenom, nom: nom, email: email, parcours: parcours,
                       message: propre_(champ_(corps, 'message'), 1000), canal: 'mail', alerte: alerte});
  if (!r.ok) incompris_(msg, email, r.erreur);
}

/** Date de la sortie écrite dans l'objet : 19/12/2026, 19/12/26, 19-12, 19/12 ou « 19 décembre (2026) ».
 *  Sans année : la sortie du calendrier à cette date la plus proche à venir. */
function dateDuSujet_(texte) {
  const t = simple_(texte);
  const MOIS = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin', 'juillet', 'aout', 'septembre', 'octobre', 'novembre', 'decembre'];
  let j, mo, an, brut;
  let m = t.match(/(\d{1,2})\s*[\/.\-]\s*(\d{1,2})(?:\s*[\/.\-]\s*(\d{2,4}))?/);
  if (m) { j = +m[1]; mo = +m[2]; an = m[3]; brut = m[0]; }
  else {
    m = t.match(new RegExp('(\\d{1,2})(?:er)?\\s+(' + MOIS.join('|') + ')(?:\\s+(\\d{4}))?'));
    if (!m) return null;
    j = +m[1]; mo = MOIS.indexOf(m[2]) + 1; an = m[3]; brut = m[0];
  }
  if (!(j >= 1 && j <= 31 && mo >= 1 && mo <= 12)) return null;
  const jjmm = ('0' + mo).slice(-2) + '-' + ('0' + j).slice(-2);
  if (an) return {date: (an.length === 2 ? '20' + an : an) + '-' + jjmm, texte: brut};
  const auj = Utilities.formatDate(new Date(), 'Europe/Paris', 'yyyy-MM-dd');
  const a = +auj.slice(0, 4);
  const candidates = [a + '-' + jjmm, (a + 1) + '-' + jjmm].filter(d => d >= auj);
  const connue = candidates.find(d => sorties_()[d]);
  return {date: connue || candidates[0] || (a + 1) + '-' + jjmm, texte: brut};
}

/** Parcours écrit librement (« circuit court », « le long », « moyen », « family », « 58 », « 58 km »)
 *  → libellé exact d'un des parcours prévus. Mots clés : Long = le plus long, Court = le plus court,
 *  Moyen = celui du milieu (s'il n'y en a pas, le plus court). Renvoie '' si rien ne correspond. */
function choisirParcours_(texte, liste) {
  liste = liste || [];
  const t = simple_(texte);
  if (!t || !liste.length) return '';
  const exact = liste.find(c => simple_(c.libelle) === t);
  if (exact) return exact.libelle;
  const km = c => parseFloat(String(c.km || '').split('-')[0].replace(',', '.')) || 0;
  const family = liste.filter(c => c.type === 'Family');
  const autres = liste.filter(c => c.type !== 'Family').sort((a, b) => km(b) - km(a));
  if (/\bfamil(y|le|ial)/.test(t) && family.length) return family[0].libelle;
  const motCle = /\b(long|longue|grand)\b/.test(t) ? 'long' : /\b(moyen|moyenne|intermediaire|milieu)\b/.test(t) ? 'moyen'
               : /\b(court|courte|petit|petite)\b/.test(t) ? 'court' : '';
  if (motCle && autres.length) {
    if (motCle === 'long') return autres[0].libelle;
    if (motCle === 'court') return autres[autres.length - 1].libelle;
    const moyen = autres.find(c => c.niveau === 'Moyen');
    return (moyen || autres[autres.length - 1]).libelle;   // pas de moyen : le plus court
  }
  // Une distance écrite (« 58 », « 58 km ») : le parcours le plus proche (à 15 % près).
  const n = (t.match(/\d+(?:[.,]\d+)?/g) || []).map(x => parseFloat(x.replace(',', '.'))).find(x => x >= 5 && x <= 400);
  if (n) {
    const proche = liste.filter(c => c.km).sort((a, b) => Math.abs(km(a) - n) - Math.abs(km(b) - n))[0];
    if (proche && Math.abs(km(proche) - n) <= Math.max(3, km(proche) * 0.15)) return proche.libelle;
  }
  return '';
}

/** Première ligne utile d'un mail sans étiquettes : « Nom Prénom [parcours…] ».
 *  L'ordre est vérifié avec le nom affiché de l'expéditeur quand c'est possible. */
function lireLigneLibre_(corps, nomAffiche) {
  const ignorer = /^(bonjour|bonsoir|salut|hello|coucou|merci|cordialement|bien\s|a\s+bientot|sportivement|envoye|sent|le\s.+a\s+ecrit|--)/;
  const lignes = corps.split(/\r?\n/).map(l => l.trim()).filter(l => l && !/^>/.test(l));
  for (const ligne of lignes) {
    if (ignorer.test(simple_(ligne)) || /[:@]/.test(ligne)) continue;
    const mots = propre_(ligne, 120).replace(/[,;]/g, ' ').split(/\s+/).filter(Boolean);
    if (mots.length < 2 || !/^[A-Za-zÀ-ÿ'’-]+$/.test(mots[0]) || !/^[A-Za-zÀ-ÿ'’-]+$/.test(mots[1])) continue;
    const affiche = simple_(nomAffiche).split(' ');
    let nom = mots[0], prenom = mots[1];
    // L'expéditeur s'affiche « Maurice Fauvel » et la ligne commence par Maurice : ordre Prénom Nom.
    if (affiche.length > 1 && affiche[0] === simple_(mots[0]) && affiche.indexOf(simple_(mots[1])) > 0) { prenom = mots[0]; nom = mots[1]; }
    const majuscule = t => t.toLowerCase().replace(/(^|[-'’])(\S)/g, (x, sep, c) => sep + c.toUpperCase());
    return {ligne: propre_(ligne, 120), prenom: majuscule(prenom), nom: nom === nom.toUpperCase() ? nom : majuscule(nom), parcours: mots.slice(2).join(' ')};
  }
  return null;
}

function incompris_(msg, email, raison) {
  if (!emailValide_(email)) return;
  MailApp.sendEmail({to: email, replyTo: PRESIDENT.email, name: NOM_CLUB,
    subject: NOM_CLUB + ' – Demande non prise en compte : ' + (msg.getSubject() || ''),
    body: ['Bonjour,', '', 'Nous n\'avons pas pu prendre en compte ton message (' + raison + ').', '',
           'Merci de renvoyer le mail type :', '',
           'Objet : Inscription ' + NOM_CLUB + ' JJ/MM/AAAA   (la date de la sortie)',
           'Nom : …', 'Prénom : …', 'Parcours : …   (long, moyen, court, family ou la distance)', '',
           'Pour annuler : même mail avec l\'objet « Désinscription ' + NOM_CLUB + ' JJ/MM/AAAA ».', '',
           'Pour toute question, réponds à ce message : il arrivera chez le président.', '', NOM_CLUB].join('\n')});
}

/* ---------- Mail type du président : ajouter / retirer des inscrits ----------
 * Objet : « Inscrits ÔGravel JJ/MM/AAAA ». Une personne par ligne :
 *   + Prénom Nom ; e-mail (facultatif) ; parcours (facultatif)   → ajout
 *   - Prénom Nom                                                   → retrait
 * Les autres lignes (bonjour, signature…) sont ignorées. Réponse : un récapitulatif.
 * Autorisés : le président, plus les adresses de la propriété du script ADMINS_MAIL (séparées par des virgules). */
function simple_(t) { return String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/\s+/g, ' ').trim(); }

function listePresident_(msg, email, date, corps) {
  const admins = [PRESIDENT.email].concat(String(PropertiesService.getScriptProperties().getProperty('ADMINS_MAIL') || '').split(','))
    .map(x => x.trim().toLowerCase()).filter(Boolean);
  if (admins.indexOf(email) < 0) return incompris_(msg, email, 'ce mail type est réservé au président');
  const sortie = sorties_()[date];
  const destinataire = email;
  if (!sortie) {
    MailApp.sendEmail({to: destinataire, name: NOM_CLUB, subject: NOM_CLUB + ' – Liste non prise en compte : ' + msg.getSubject(),
      body: 'Il n\'y a pas de sortie ÔGravel le ' + date.split('-').reverse().join('/') + ' dans le calendrier. Vérifie la date de l\'objet.\n\n' + NOM_CLUB});
    return;
  }
  const f = feuille_();
  const bilan = [];
  // On ne lit que le message lui-même, pas l'historique cité en dessous.
  const lignes = corps.split(/\r?\n/).map(l => l.trim()).filter(l => !/^>/.test(l));
  lignes.forEach(ligne => {
    const mt = ligne.match(/^([+\-–])\s*([A-Za-zÀ-ÿ].*)$/);  // « -- » de signature ignoré
    if (!mt) return;
    const morceaux = mt[2].split(/\s*;\s*/);
    const mots = propre_(morceaux[0], 100).split(' ').filter(Boolean);
    const prenom = mots.shift() || '', nom = mots.join(' ');
    const qui = (prenom + ' ' + nom).trim();
    if (!prenom) return;
    const existante = lignes_().find(l => l.date_sortie === date && l.statut === 'demande' && simple_(l.prenom + ' ' + l.nom) === simple_(qui));
    if (mt[1] === '+') {
      if (!nom) { bilan.push('⚠️ ' + qui + ' : il manque le nom, ligne ignorée'); return; }
      if (existante) { bilan.push('= ' + qui + ' : déjà inscrit(e)'); return; }
      const mail = (morceaux[1] || '').trim().toLowerCase();
      const ecrit = propre_(morceaux[2] || (!emailValide_(mail) ? morceaux[1] : '') || '', 80);
      const parcours = choisirParcours_(ecrit, sortie.parcours) || ecrit;
      const maintenant = new Date(), secret = nouveauSecret_();
      f.appendRow([maintenant, date, sortie.titre, prenom, nom, emailValide_(mail) ? mail : '', parcours, '',
                   'président', secret, 'demande', maintenant]);
      if (emailValide_(mail)) mailMembre_('demande', {date: date, prenom: prenom, nom: nom, email: mail, secret: secret}, sortie);
      bilan.push('✅ ' + qui + ' ajouté(e)' + (emailValide_(mail) ? ' (confirmation envoyée à ' + mail + ')' : ''));
    } else {
      if (!existante) { bilan.push('⚠️ ' + qui + ' : introuvable dans les inscrits'); return; }
      f.getRange(existante.ligne, COLONNES.indexOf('statut') + 1, 1, 2).setValues([['desinscrit', new Date()]]);
      rangerDesinscrits_();
      bilan.push('❌ ' + qui + ' retiré(e)');
    }
  });
  const liste = listePublique_()[date] || [];
  MailApp.sendEmail({to: destinataire, name: NOM_CLUB, subject: NOM_CLUB + ' – Liste mise à jour – ' + sortie.titre + ' du ' + dateLongue_(date),
    body: [bilan.length ? bilan.join('\n') : 'Aucune ligne commençant par + ou - n\'a été trouvée.', '',
           'Inscrits (' + liste.length + ') :', liste.map(x => '• ' + x.prenom + ' ' + x.nom).join('\n') || '(aucun)', '',
           'Rappel : une personne par ligne, « + Prénom Nom ; e-mail ; parcours » pour ajouter, « - Prénom Nom » pour retirer.', '', NOM_CLUB].join('\n')});
}

/** À lancer une fois à la main : crée le tableau et le déclencheur des mails. */
function installer() {
  feuille_();
  rangerDesinscrits_();
  ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'lireMails').forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('lireMails').timeBased().everyMinutes(10).create();
  Logger.log('Tableau : ' + SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('TABLEAU')).getUrl());
}
