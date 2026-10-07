// Année du pied de page
document.getElementById('annee').textContent = new Date().getFullYear();

// Menu mobile
const btn = document.querySelector('.menu-btn');
const nav = document.getElementById('nav');
btn.addEventListener('click', () => {
  const open = nav.classList.toggle('open');
  btn.setAttribute('aria-expanded', open);
});
nav.addEventListener('click', e => {
  if (e.target.tagName === 'A') { nav.classList.remove('open'); btn.setAttribute('aria-expanded', false); }
});

// ---------- Veille : lit veille.json généré par veille.py ----------
const liste = document.getElementById('veille-liste');
const cartes = document.getElementById('veille-cartes');
const titreCartes = document.getElementById('cartes-titre');
const info = document.getElementById('veille-info');
const filtre = document.getElementById('filtre');
const NB_CARTES = 4;
let articles = [];
let maj = null;

// Minuscules et sans accents, pour que "rancongiciel" trouve "rançongiciel"
const norm = t => (t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const dateFr = d => new Date(d).toLocaleDateString('fr-FR');

// Résumé court, coupé proprement à la fin d'un mot
function court(t, n = 170) {
  t = (t || '').trim();
  if (!t) return "Résumé non disponible : ouvre l'article pour le lire.";
  if (t.length <= n) return t;
  const coupe = t.slice(0, n);
  const fin = coupe.lastIndexOf(' ');
  return coupe.slice(0, fin > 80 ? fin : n).replace(/[\s,;:.\-–]+$/, '') + '…';
}

// Les articles récents et pertinents passent devant : la sélection change donc
// à chaque nouvelle mise à jour de veille.json (tous les jours).
function pertinence(a, termes) {
  const ageJours = (Date.now() - new Date(a.date)) / 864e5;
  let p = (a.score || 0) - ageJours * 0.5;
  const titre = norm(a.titre), resume = norm(a.resume);
  termes.forEach(m => { p += (titre.includes(m) ? 5 : 0) + (resume.includes(m) ? 2 : 0); });
  return p;
}

function creerCarte(a) {
  const carte = document.createElement('article');
  carte.className = 'card';
  const h3 = document.createElement('h3');
  h3.textContent = a.titre;
  const meta = document.createElement('p');
  meta.className = 'meta';
  meta.textContent = a.source + ' · ' + dateFr(a.date);
  const p = document.createElement('p');
  p.textContent = court(a.resume);
  const lien = document.createElement('a');
  lien.href = a.lien; lien.target = '_blank'; lien.rel = 'noopener noreferrer';
  lien.textContent = "Lire l'article";
  carte.append(h3, meta, p, lien);
  return carte;
}

function creerLigne(a) {
  const li = document.createElement('li');
  const lien = document.createElement('a');
  lien.href = a.lien; lien.textContent = a.titre; lien.target = '_blank'; lien.rel = 'noopener noreferrer';
  const meta = document.createElement('div');
  meta.className = 'meta';
  meta.textContent = a.source + ' · ' + dateFr(a.date);
  const p = document.createElement('p');
  p.textContent = a.resume;
  li.append(lien, meta, p);
  return li;
}

function afficher() {
  const q = filtre.value.trim();
  const termes = norm(q).split(/\s+/).filter(Boolean);
  const res = articles.filter(a => {
    const texte = norm(a.titre + ' ' + a.resume + ' ' + a.source);
    return termes.every(m => texte.includes(m));
  });

  // Les 4 blocs : les articles les plus pertinents parmi les résultats
  const top = [...res].sort((a, b) => pertinence(b, termes) - pertinence(a, termes)).slice(0, NB_CARTES);
  cartes.replaceChildren(...top.map(creerCarte));
  titreCartes.textContent = termes.length
    ? 'Articles les plus pertinents pour « ' + q + ' »'
    : 'À la une : les articles les plus pertinents du moment';
  if (!top.length) {
    const vide = document.createElement('p');
    vide.className = 'meta';
    vide.textContent = 'Aucun article ne correspond à ces mots-clés.';
    cartes.replaceChildren(vide);
  }

  // La liste complète garde tous les articles filtrés
  liste.replaceChildren(...res.map(creerLigne));
  if (!res.length) {
    const vide = document.createElement('li');
    vide.className = 'meta';
    vide.textContent = 'Aucun article ne correspond.';
    liste.replaceChildren(vide);
  }
  info.textContent = res.length + ' article(s)' + (maj ? ' · mis à jour le ' + dateFr(maj) : '');
}

fetch('veille.json')
  .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then(data => {
    articles = data.articles || [];
    maj = data.maj || null;
    afficher();
  })
  .catch(() => {
    const msg = 'Aucune veille chargée. Lance veille.py puis publie veille.json.';
    liste.innerHTML = '<li class="meta">' + msg + '</li>';
    cartes.innerHTML = '<p class="meta">' + msg + '</p>';
  });
filtre.addEventListener('input', afficher);
