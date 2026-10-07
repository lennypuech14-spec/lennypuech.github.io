#!/usr/bin/env python3
"""
Outil de veille technologique : ransomwares et résilience des infrastructures.
Auteur : Lenny PUECH (BTS SIO SISR)

Fonctionnement :
  1. Télécharge des flux RSS/Atom de sources officielles et spécialisées.
  2. Garde les articles récents qui contiennent au moins un mot-clé.
  3. Calcule un score de pertinence et supprime les doublons.
  4. Écrit veille.json (lu par le site) et veille.md (rapport lisible).

Utilisation :
  python veille.py                 # 14 derniers jours
  python veille.py --jours 30      # 30 derniers jours
Aucune bibliothèque externe n'est nécessaire (Python 3.8+).
"""
import argparse
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

# Vérifie que ces adresses fonctionnent toujours : les sites changent parfois d'URL.
SOURCES = {
    "CERT-FR (alertes)": "https://www.cert.ssi.gouv.fr/alerte/feed/",
    "CERT-FR (avis)": "https://www.cert.ssi.gouv.fr/avis/feed/",
    "Cybermalveillance.gouv.fr": "https://www.cybermalveillance.gouv.fr/feed/",
    "ZATAZ": "https://www.zataz.com/feed/",
    "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
    "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
}

# Mot-clé -> poids (plus le poids est élevé, plus l'article est pertinent)
MOTS_CLES = {
    "ransomware": 3, "rançongiciel": 3, "rancongiciel": 3, "ransom": 2,
    "sauvegarde": 3, "backup": 3, "immuable": 3, "immutable": 3,
    "chiffrement": 2, "lockbit": 2, "blackcat": 2, "akira": 2, "play ransomware": 2,
    "veeam": 2, "restauration": 2, "plan de continuité": 2, "pca": 1, "pra": 1,
    "vulnérabilité": 1, "vulnerability": 1, "zero-day": 1, "cve-": 1,
    "active directory": 1, "esxi": 2, "proxmox": 1, "vpn": 1, "extorsion": 1,
}

SEUIL = 3  # score minimum pour garder un article


def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": "veille-btssio/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read()


def nettoyer(texte):
    texte = re.sub(r"<[^>]+>", " ", texte or "")
    texte = html.unescape(texte)
    return re.sub(r"\s+", " ", texte).strip()


def lire_date(texte):
    if not texte:
        return None
    try:
        d = parsedate_to_datetime(texte)  # format RSS
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(texte.replace("Z", "+00:00"))  # format Atom
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def balise(el, nom):
    """Cherche une balise en ignorant les espaces de noms XML."""
    for enfant in el:
        if enfant.tag.split("}")[-1] == nom:
            return enfant
    return None


def lire_flux(nom, url):
    racine = ET.fromstring(telecharger(url))
    items = [e for e in racine.iter() if e.tag.split("}")[-1] in ("item", "entry")]
    for it in items:
        titre = balise(it, "title")
        lien = balise(it, "link")
        desc = balise(it, "description") or balise(it, "summary") or balise(it, "content")
        date = balise(it, "pubDate") or balise(it, "published") or balise(it, "updated")
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
    texte = (article["titre"] + " " + article["resume"]).lower()
    return sum(p for mot, p in MOTS_CLES.items() if mot in texte)


def main():
    ap = argparse.ArgumentParser(description="Outil de veille ransomwares / sauvegarde")
    ap.add_argument("--jours", type=int, default=14, help="période analysée (défaut : 14)")
    args = ap.parse_args()
    limite = datetime.now(timezone.utc) - timedelta(days=args.jours)

    retenus, vus = [], set()
    for nom, url in SOURCES.items():
        try:
            n = 0
            for a in lire_flux(nom, url):
                a["score"] = score(a)
                cle = re.sub(r"\W+", "", a["titre"].lower())
                if a["date"] < limite or a["score"] < SEUIL or cle in vus:
                    continue
                vus.add(cle)
                retenus.append(a)
                n += 1
            print(f"[OK]    {nom} : {n} article(s) retenu(s)")
        except Exception as e:  # une source en panne ne bloque pas les autres
            print(f"[ERREUR] {nom} : {e}", file=sys.stderr)

    retenus.sort(key=lambda a: (a["date"], a["score"]), reverse=True)

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

    print(f"\n{len(retenus)} article(s) écrits dans veille.json et veille.md")


if __name__ == "__main__":
    main()
