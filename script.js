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

// Veille : lit veille.json généré par veille.py
const liste = document.getElementById('veille-liste');
const info = document.getElementById('veille-info');
const filtre = document.getElementById('filtre');
let articles = [];

function afficher() {
  const q = filtre.value.trim().toLowerCase();
  const res = articles.filter(a => (a.titre + ' ' + a.resume + ' ' + a.source).toLowerCase().includes(q));
  liste.innerHTML = '';
  res.forEach(a => {
    const li = document.createElement('li');
    const lien = document.createElement('a');
    lien.href = a.lien; lien.textContent = a.titre; lien.target = '_blank'; lien.rel = 'noopener noreferrer';
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = a.source + ' · ' + new Date(a.date).toLocaleDateString('fr-FR');
    const p = document.createElement('p');
    p.textContent = a.resume;
    li.append(lien, meta, p);
    liste.appendChild(li);
  });
  info.textContent = res.length + ' article(s)';
  if (!res.length) liste.innerHTML = '<li class="meta">Aucun article ne correspond.</li>';
}

fetch('veille.json')
  .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then(data => {
    articles = data.articles || [];
    if (data.maj) info.dataset.maj = data.maj;
    afficher();
    if (data.maj) info.textContent += ' · mis à jour le ' + new Date(data.maj).toLocaleDateString('fr-FR');
  })
  .catch(() => {
    liste.innerHTML = '<li class="meta">Aucune veille chargée. Lance veille.py puis publie veille.json.</li>';
  });
filtre.addEventListener('input', afficher);
