#!/usr/bin/env python3
"""
Outil de veille technologique : ransomwares et résilience des infrastructures.
Auteur : Lenny PUECH (BTS SIO SISR)

Fonctionnement :
  1. Télécharge des flux RSS/Atom de sources officielles et spécialisées.
  2. Garde les articles récents qui parlent du sujet (mots-clés pondérés).
  3. Si peu d'articles passent le filtre, complète avec les plus proches du sujet.
  4. Écrit veille.json (lu par le site) et veille.md (rapport lisible).

Utilisation :
  python veille.py                          # 30 derniers jours
  python veille.py --jours 60 --seuil 3     # période plus longue, filtre plus strict
Aucune bibliothèque externe n'est nécessaire (Python 3.8+).
"""
import argparse
import html
import json
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# Si une source affiche [ERREUR], son adresse a peut-être changé : remplace-la.
SOURCES = {
    "CERT-FR (alertes)": "https://www.cert.ssi.gouv.fr/alerte/feed/",
    "CERT-FR (avis)": "https://www.cert.ssi.gouv.fr/avis/feed/",
    "Cybermalveillance.gouv.fr": "https://www.cybermalveillance.gouv.fr/feed/",
    "ZATAZ": "https://www.zataz.com/feed/",
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
    "Krebs on Security": "https://krebsonsecurity.com/feed/",
    "SecurityWeek": "https://feeds.feedburner.com/securityweek",
    "The Register (sécurité)": "https://www.theregister.com/security/headlines.atom",
}

# Mot-clé -> poids (accents et majuscules ignorés)
MOTS_CLES = {
    "ransomware": 3, "rancongiciel": 3, "ransom": 2, "extorsion": 2, "extortion": 2,
    "sauvegarde": 3, "backup": 3, "immuable": 3, "immutable": 3, "restauration": 2,
    "restore": 1, "recovery": 2, "continuite d'activite": 2, "plan de reprise": 2,
    "chiffrement": 2, "encrypt": 2, "lockbit": 2, "blackcat": 2, "alphv": 2, "akira": 2,
    "clop": 2, "qilin": 2, "veeam": 2, "esxi": 2, "vmware": 1, "proxmox": 1, "nas": 1,
    "active directory": 2, "cyberattaque": 2, "cyberattack": 2, "fuite de donnees": 1,
    "data breach": 1, "vulnerabilite": 1, "vulnerability": 1, "zero-day": 1, "cve-": 1,
    "vpn": 1, "pare-feu": 1, "firewall": 1, "hopital": 1, "collectivite": 1,
}
MOTS_CLES = {unicodedata.normalize("NFD", k): p for k, p in MOTS_CLES.items()}
MIN_ARTICLES = 10  # on complète jusqu'à ce nombre si le filtre est trop strict


def norm(texte):
    texte = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def telecharger(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def nettoyer(texte):
    texte = re.sub(r"<[^>]+>", " ", texte or "")
    return re.sub(r"\s+", " ", html.unescape(texte)).strip()


def lire_date(texte):
    if not texte:
        return None
    texte = texte.strip()
    try:
        d = parsedate_to_datetime(texte)  # format RSS
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(texte.replace("Z", "+00:00"))  # format Atom
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def balise(el, *noms):
    """Cherche une balise en ignorant les espaces de noms XML."""
    for enfant in el:
        if enfant.tag.split("}")[-1] in noms:
            return enfant
    return None


def lire_flux(nom, url):
    racine = ET.fromstring(telecharger(url))
    items = [e for e in racine.iter() if e.tag.split("}")[-1] in ("item", "entry")]
    for it in items:
        titre = balise(it, "title")
        lien = balise(it, "link")
        desc = balise(it, "description", "summary", "content")
        date = balise(it, "pubDate", "published", "updated", "date")
        href = (lien.get("href") or lien.text) if lien is not None else ""
        d = lire_date(date.text if date is not None else None)
        if titre is None or not href or d is None:
            continue
        yield {
            "titre": nettoyer(titre.text),
            "lien": href.strip(),
            "resume": nettoyer(desc.text if desc is not None else "")[:280],
            "date": d,
            "source": nom,
        }


def score(article):
    texte = norm(article["titre"] + " " + article["resume"])
    return sum(p for mot, p in MOTS_CLES.items() if re.search(r"\b" + re.escape(mot), texte))


def main():
    ap = argparse.ArgumentParser(description="Outil de veille ransomwares / sauvegarde")
    ap.add_argument("--jours", type=int, default=30, help="période analysée (défaut : 30)")
    ap.add_argument("--seuil", type=int, default=2, help="score minimum (défaut : 2)")
    args = ap.parse_args()
    limite = datetime.now(timezone.utc) - timedelta(days=args.jours)

    candidats, vus, total_lus = [], set(), 0
    for nom, url in SOURCES.items():
        try:
            lus = recents = 0
            for a in lire_flux(nom, url):
                lus += 1
                if a["date"] < limite:
                    continue
                recents += 1
                a["score"] = score(a)
                cle = re.sub(r"\W+", "", a["titre"].lower())
                if a["score"] < 1 or cle in vus:
                    continue
                vus.add(cle)
                candidats.append(a)
            total_lus += lus
            print(f"[OK]     {nom} : {lus} lus, {recents} récents")
        except Exception as e:  # une source en panne ne bloque pas les autres
            print(f"[ERREUR] {nom} : {e}", file=sys.stderr)

    if total_lus == 0:
        print("Aucune source n'a répondu : vérifie les adresses de SOURCES.", file=sys.stderr)
        sys.exit(1)

    candidats.sort(key=lambda a: (a["score"], a["date"]), reverse=True)
    retenus = [a for a in candidats if a["score"] >= args.seuil]
    if len(retenus) < MIN_ARTICLES:  # on complète avec les plus proches du sujet
        retenus = candidats[:MIN_ARTICLES]
    retenus.sort(key=lambda a: a["date"], reverse=True)

    print(f"\n{total_lus} articles lus, {len(candidats)} liés au sujet, {len(retenus)} retenus")

    sortie = {
        "maj": datetime.now(timezone.utc).isoformat(),
        "sujet": "Ransomwares et résilience des infrastructures",
        "articles": [{**a, "date": a["date"].isoformat()} for a in retenus],
    }
    with open("veille.json", "w", encoding="utf-8") as f:
        json.dump(sortie, f, ensure_ascii=False, indent=2)

    with open("veille.md", "w", encoding="utf-8") as f:
        f.write(f"# Veille du {datetime.now():%d/%m/%Y} : ransomwares et résilience\n\n")
        for a in retenus:
            f.write(f"## {a['titre']}\n- Source : {a['source']} ({a['date']:%d/%m/%Y})\n"
                    f"- Pertinence : {a['score']}\n- Lien : {a['lien']}\n\n{a['resume']}\n\n")


if __name__ == "__main__":
    main()
