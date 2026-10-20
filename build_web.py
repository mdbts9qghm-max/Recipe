#!/usr/bin/env python3
"""Erzeugt die Web-App in web/ aus Rezepten, Wochenplänen und Einkaufslisten.

    python3 build_web.py

Handgeschriebene, feste Dateien in web/: index.html, app.css, app.js, rezept.js,
manifest.webmanifest, icons/. Dieses Skript erzeugt daraus:
  web/data.js        Rezeptliste, Wochenpläne und Einkaufslisten für die App
  web/r/<name>.html  eine Seite pro Rezept (mit schema.org-JSON-LD für MacroFactor)

Erwartetes Format der Wochenpläne (für „Heute“): eine Übersichtstabelle mit den Spalten
| Tag | Frühstück | Mittag | Abend |, Rezepte als Links auf rezepte/…/name.md, und pro Tag
ein Abschnitt „## Montag …“ mit einer Zeile „Tagessumme: …“.
"""

import datetime
import html
import json
import re
import shutil
from pathlib import Path

import naehrwerte as nw

BASIS = Path(__file__).resolve().parent
WEB = BASIS / "web"
REZEPT_WEB = WEB / "r"
WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MAHLZEITEN = ["Frühstück", "Mittag", "Abend"]


# ---------------------------------------------------------------- Markdown

def inline(text, link):
    """Inline-Markdown: **fett**, `code`, [Text](Ziel). link(ziel) passt Links an."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)",
                  lambda m: f'<a href="{html.escape(link(m.group(2)))}">{m.group(1)}</a>', text)


def tabellenzeile(zeile):
    return [z.strip() for z in zeile.strip().strip("|").split("|")]


def md_zu_html(text, link=lambda z: z, checkbox_id=None):
    """Kleiner Markdown-Konverter für Überschriften, Tabellen, Listen und Absätze.
    checkbox_id(n) liefert die ID für die n-te Checkbox (- [ ])."""
    out = []
    zeilen = text.splitlines()
    i = 0
    n_box = 0
    while i < len(zeilen):
        z = zeilen[i]
        s = z.strip()
        if not s:
            i += 1
            continue
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            ebene = len(m.group(1)) + 1
            out.append(f"<h{ebene}>{inline(m.group(2), link)}</h{ebene}>")
            i += 1
            continue
        if s.startswith("|"):
            block = []
            while i < len(zeilen) and zeilen[i].strip().startswith("|"):
                block.append(tabellenzeile(zeilen[i]))
                i += 1
            kopf, rest = block[0], [r for r in block[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            out.append('<div class="tabelle"><table><thead><tr>'
                       + "".join(f"<th>{inline(c, link)}</th>" for c in kopf) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c, link)}</td>" for c in r) + "</tr>"
                                 for r in rest)
                       + "</tbody></table></div>")
            continue
        if re.match(r"[-*] ", s):
            items = []
            while i < len(zeilen) and re.match(r"\s*[-*] ", zeilen[i]):
                inhalt = re.sub(r"^\s*[-*] ", "", zeilen[i])
                box = re.match(r"\[( |x)\] (.*)", inhalt)
                if box and checkbox_id:
                    cid = checkbox_id(n_box)
                    n_box += 1
                    items.append(f'<li class="check"><label><input type="checkbox" data-id="{cid}"'
                                 f'{" checked" if box.group(1) == "x" else ""}> '
                                 f"<span>{inline(box.group(2), link)}</span></label></li>")
                else:
                    items.append(f"<li>{inline(inhalt, link)}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if re.match(r"\d+\. ", s):
            items = []
            while i < len(zeilen) and re.match(r"\s*\d+\. ", zeilen[i]):
                items.append(f"<li>{inline(re.sub(r'^\s*\d+\. ', '', zeilen[i]), link)}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        absatz = [s]
        i += 1
        while i < len(zeilen) and zeilen[i].strip() and not re.match(r"(#|\||[-*] |\d+\. )", zeilen[i].strip()):
            absatz.append(zeilen[i].strip())
            i += 1
        out.append(f"<p>{inline(' '.join(absatz), link)}</p>")
    return "\n".join(out)


def ohne_md(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)


# ---------------------------------------------------------------- Rezepte

def abschnitte(text):
    """{Überschrift: Inhalt} aller '## '-Abschnitte."""
    teile = re.split(r"^## ", text, flags=re.M)[1:]
    return {t.split("\n", 1)[0].strip(): (t.split("\n", 1) + [""])[1] for t in teile}


def zeit_teile(zeile):
    werte = {}
    for name, schluessel in (("Vorbereitung", "vorbereitung"), ("Kochen", "kochen"), ("Gesamt", "gesamt")):
        m = re.search(rf"{name}\s*(\d+)\s*min", zeile)
        werte[schluessel] = int(m.group(1)) if m else None
    return werte


def zutaten(abschnitt):
    zeilen = []
    for z in abschnitt.splitlines():
        if not z.strip().startswith("|"):
            continue
        zellen = tabellenzeile(z)
        if len(zellen) < 2 or zellen[0] in ("Zutat",) or re.fullmatch(r"-+", zellen[0]):
            continue
        zeilen.append({"zutat": ohne_md(zellen[0]), "menge": zellen[1],
                       "hinweis": zellen[2] if len(zellen) > 2 else "",
                       "gruppe": not zellen[1]})
    return zeilen


def macrofactor_zeile(z):
    m = re.match(r"([\d.,]+)\s*(g|ml)\b", z["menge"])
    if not m:
        return None
    return f"{m.group(1)} {m.group(2)} {z['zutat']}"


def schritte(abschnitt):
    """Nummerierte Schritte aus Mise en place und Zubereitung, für den Kochmodus."""
    liste = []
    teil = "Vorbereitung"
    for z in abschnitt.splitlines():
        s = z.strip()
        if s.startswith("### "):
            teil = "Vorbereitung" if "Mise" in s else "Zubereitung"
        m = re.match(r"\d+\. (.*)", s)
        if m:
            liste.append({"teil": teil, "text": m.group(1)})
    return liste


def lies_rezept(pfad, db):
    info = nw.rezept_info(pfad, db)
    text = info["text"]
    teile = abschnitte(text)
    zut_titel = next(k for k in teile if k.startswith("Zutaten"))
    zubereitung = teile.get("Zubereitung", "")
    gewicht = re.search(r"\*\*Gewicht[^*]*:\*\*\s*(.+)", zubereitung)
    slug = pfad.stem
    return {
        "slug": slug,
        "pfad": pfad.relative_to(BASIS).as_posix(),
        "ordner": pfad.parent.name,
        "titel": info["titel"],
        "kategorien": info["kategorien"],
        "kueche": info["kueche"],
        "mahlzeit": info["mahlzeit"],
        "inspiration": info["inspiration"],
        "sterne": info["sterne"],
        "bewertung": nw.kopf(text, "Bewertung"),
        "schwierigkeit": (re.search(r"\*\*Schwierigkeit:\*\*\s*(\S+)", text) or [None, ""])[1],
        "zeit": zeit_teile(nw.kopf(text, "Zeit")),
        "zeit_text": nw.kopf(text, "Zeit"),
        "ausstattung": nw.kopf(text, "Ausstattung"),
        "portion": {k: round(v, 1) for k, v in info["portion"].items()},
        "zutaten_titel": zut_titel,
        "zutaten": zutaten(teile[zut_titel]),
        "zutaten_rest": "\n".join(z for z in teile[zut_titel].splitlines() if not z.strip().startswith("|")),
        "schritte": schritte(zubereitung),
        "zubereitung": zubereitung,
        "gewicht": ohne_md(gewicht.group(1)) if gewicht else "",
        "abschnitte": {k: teile[k] for k in ("Meal Prep & Aufbewahrung", "Varianten & Austausch", "Tipps",
                                              "Nährwert-Berechnung") if k in teile},
    }


def iso_dauer(minuten):
    return f"PT{minuten}M" if minuten is not None else None


def json_ld(r):
    p = r["portion"]
    daten = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": r["titel"],
        "recipeYield": "2",
        "recipeCategory": r["mahlzeit"],
        "recipeCuisine": r["kueche"],
        "keywords": ", ".join(r["kategorien"]),
        "prepTime": iso_dauer(r["zeit"]["vorbereitung"]),
        "cookTime": iso_dauer(r["zeit"]["kochen"]),
        "totalTime": iso_dauer(r["zeit"]["gesamt"]),
        "recipeIngredient": [z for z in map(macrofactor_zeile, r["zutaten"]) if z],
        "recipeInstructions": [{"@type": "HowToStep", "text": ohne_md(s["text"])} for s in r["schritte"]],
        "nutrition": {
            "@type": "NutritionInformation",
            "servingSize": "1 Portion",
            "calories": f"{p['kcal']:.0f} kcal",
            "proteinContent": f"{p['protein']} g",
            "fatContent": f"{p['fett']} g",
            "saturatedFatContent": f"{p['gesaettigt']} g",
            "carbohydrateContent": f"{p['kh']} g",
            "sugarContent": f"{p['zucker']} g",
            "fiberContent": f"{p['ballaststoffe']} g",
            "sodiumContent": f"{p['salz'] / 2.5 * 1000:.0f} mg",
        },
    }
    if r["inspiration"]:
        daten["description"] = ohne_md(r["inspiration"])
    return json.dumps({k: v for k, v in daten.items() if v is not None}, ensure_ascii=False, indent=1)


def rezept_link_auf_seite(ziel):
    """Links in Rezepttexten: andere Rezepte → Rezeptseiten, sonst unverändert."""
    m = re.search(r"rezepte/[^/]+/([^/]+)\.md$", ziel)
    return f"{m.group(1)}.html" if m else ziel


def zahl(x, stellen=1):
    return f"{x:.{stellen}f}".replace(".", ",")


def rezeptseite(r):
    e = html.escape
    p = r["portion"]
    lk = rezept_link_auf_seite
    chips = "".join(f'<span class="chip">{e(k)}</span>' for k in r["kategorien"])
    zutaten_html = []
    for z in r["zutaten"]:
        if z["gruppe"]:
            zutaten_html.append(f'<tr class="gruppe"><td colspan="2">{e(z["zutat"])}</td></tr>')
        else:
            hinweis = f'<div class="hinweis">{inline(z["hinweis"], lk)}</div>' if z["hinweis"] else ""
            zutaten_html.append(f'<tr><td class="menge">{inline(z["menge"], lk)}</td>'
                                f'<td>{inline(z["zutat"], lk)}{hinweis}</td></tr>')
    macrofactor = "\n".join(z for z in map(macrofactor_zeile, r["zutaten"]) if z)
    weitere = "".join(f'<section><h2>{e(t)}</h2>{md_zu_html(inhalt, lk)}</section>'
                      for t, inhalt in r["abschnitte"].items() if t != "Nährwert-Berechnung")
    berechnung = r["abschnitte"].get("Nährwert-Berechnung", "")
    kochmodus = json.dumps([{"teil": s["teil"], "html": inline(s["text"], lk)} for s in r["schritte"]],
                           ensure_ascii=False)
    bewertung = f'<p class="meta">Bewertung: {inline(r["bewertung"], lk)}</p>' if r["bewertung"] else ""
    inspiration = (f'<p class="inspiration"><strong>Inspiration:</strong> {inline(r["inspiration"], lk)}</p>'
                   if r["inspiration"] else "")
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(r["titel"])} · Rezeptbuch</title>
<meta name="theme-color" content="#f7f4ef" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#1b1a18" media="(prefers-color-scheme: dark)">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="../manifest.webmanifest">
<link rel="apple-touch-icon" href="../icons/icon-180.png">
<link rel="stylesheet" href="../app.css">
<script type="application/ld+json">
{json_ld(r)}
</script>
</head>
<body class="rezeptseite">
<header class="leiste">
  <a class="zurueck" href="../index.html#rezepte" aria-label="Zurück zum Rezeptbuch">‹ Rezepte</a>
</header>
<main>
  <h1>{e(r["titel"])}</h1>
  <div class="chips">{chips}<span class="chip kueche">{e(r["kueche"])}</span></div>
  {bewertung}
  {inspiration}
  <p class="meta">{e(r["mahlzeit"])} · 2 Portionen · {e(r["schwierigkeit"])}<br>{e(r["zeit_text"])}</p>
  <p class="meta">Ausstattung: {e(r["ausstattung"])}</p>

  <div class="makros gross">
    <div><b>{p["kcal"]:.0f}</b><span>kcal</span></div>
    <div><b>{zahl(p["protein"])}</b><span>g Protein</span></div>
    <div><b>{zahl(p["fett"])}</b><span>g Fett</span></div>
    <div><b>{zahl(p["kh"])}</b><span>g KH</span></div>
  </div>
  <p class="meta klein">pro Portion · davon gesättigt {zahl(p["gesaettigt"])} g · Zucker {zahl(p["zucker"])} g ·
    Ballaststoffe {zahl(p["ballaststoffe"])} g · Salz {zahl(p["salz"], 2)} g</p>

  <div class="knoepfe">
    <button class="primaer" id="kochmodus-start">Kochmodus starten</button>
    <button id="macrofactor">Für MacroFactor kopieren</button>
  </div>
  <div class="hinweisbox">
    <strong>MacroFactor:</strong> Link dieser Seite in MacroFactor importieren oder die kopierte Zutatenliste einfügen.
    Danach das <strong>Gesamtgewicht nach dem Kochen wiegen</strong> und in MacroFactor eintragen, dann kannst du deine Portion nach Gramm loggen.
    {f'<br>Richtwert: {e(r["gewicht"])}' if r["gewicht"] else ""}
  </div>

  <section>
    <h2>{e(r["zutaten_titel"])}</h2>
    <div class="tabelle"><table class="zutaten"><tbody>{"".join(zutaten_html)}</tbody></table></div>
    {md_zu_html(r["zutaten_rest"], lk)}
  </section>
  <section class="zubereitung">
    <h2>Zubereitung</h2>
    {md_zu_html(r["zubereitung"], lk)}
  </section>
  {weitere}
  <details>
    <summary>Nährwert-Berechnung</summary>
    {md_zu_html(berechnung, lk)}
  </details>
</main>

<div id="kochmodus" class="kochmodus" hidden>
  <div class="km-kopf">
    <span id="km-zaehler"></span>
    <button id="km-schliessen" aria-label="Kochmodus beenden">Fertig</button>
  </div>
  <div id="km-teil" class="km-teil"></div>
  <div id="km-text" class="km-text"></div>
  <div class="km-fuss">
    <button id="km-zurueck">‹ Zurück</button>
    <button id="km-weiter" class="primaer">Weiter ›</button>
  </div>
  <div id="km-wach" class="km-wach"></div>
</div>

<textarea id="macrofactor-text" hidden>{e(macrofactor)}</textarea>
<script>window.KOCHSCHRITTE = {kochmodus};</script>
<script src="../rezept.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------- Wochenpläne & Einkaufslisten

def ohne_titel(text):
    """Erste '# '-Überschrift weglassen, die App zeigt ihren eigenen Titel."""
    return re.sub(r"\A\s*# [^\n]*\n", "", text)


def kw_aus_name(name):
    m = re.match(r"KW-(\d{1,2})-(\d{4})", name)
    return (int(m.group(1)), int(m.group(2))) if m else None


def plan_link(ziel):
    m = re.search(r"rezepte/[^/]+/([^/]+)\.md$", ziel)
    return f"r/{m.group(1)}.html" if m else ziel


def lies_plan(pfad):
    text = pfad.read_text(encoding="utf-8")
    kw, jahr = kw_aus_name(pfad.stem)
    montag = datetime.date.fromisocalendar(jahr, kw, 1)
    tage = {}
    # Übersichtstabelle: erste Spalte = Wochentag, Spalten mit Frühstück/Mittag/Abend
    kopf = None
    for z in text.splitlines():
        if not z.strip().startswith("|"):
            kopf = None
            continue
        zellen = tabellenzeile(z)
        if kopf is None:
            kopf = zellen
            continue
        if all(re.fullmatch(r":?-+:?", c) for c in zellen):
            continue
        tag = next((t for t in WOCHENTAGE if ohne_md(zellen[0]).startswith(t[:2])), None)
        if not tag:
            continue
        for spalte, zelle in zip(kopf[1:], zellen[1:]):
            mahlzeit = next((m for m in MAHLZEITEN if m.lower() in spalte.lower()), None)
            if mahlzeit:
                tage.setdefault(tag, {})[mahlzeit] = inline(zelle, plan_link)
    # Tagessummen aus den Tagesabschnitten
    summen = {}
    for teil in re.split(r"^## ", text, flags=re.M)[1:]:
        titel = teil.split("\n", 1)[0]
        tag = next((t for t in WOCHENTAGE if titel.startswith(t)), None)
        m = re.search(r"^.*Tagessumme.*$", teil, re.M)
        if tag and m:
            zeile = re.sub(r"^\s*[-*]\s*", "", m.group(0))
            summen[tag] = inline(re.sub(r"^\**Tagessumme\**:?\**\s*", "", zeile), plan_link)
    return {
        "name": pfad.stem,
        "titel": f"KW {kw}/{jahr}",
        "montag": montag.isoformat(),
        "tage": tage,
        "summen": summen,
        "html": md_zu_html(ohne_titel(text), plan_link),
    }


def lies_liste(pfad):
    text = pfad.read_text(encoding="utf-8")
    kw = kw_aus_name(pfad.stem)
    return {
        "name": pfad.stem,
        "titel": f"KW {kw[0]}/{kw[1]}" if kw else pfad.stem,
        "html": md_zu_html(ohne_titel(text), plan_link, checkbox_id=lambda n: f"{pfad.stem}-{n}"),
    }


# ---------------------------------------------------------------- Build

def main():
    db = nw.lade_zutaten()
    rezepte = [lies_rezept(p, db) for p in nw.alle_rezepte()]
    rezepte.sort(key=lambda r: r["titel"])

    if REZEPT_WEB.exists():
        shutil.rmtree(REZEPT_WEB)
    REZEPT_WEB.mkdir(parents=True)
    for r in rezepte:
        (REZEPT_WEB / f"{r['slug']}.html").write_text(rezeptseite(r), encoding="utf-8")

    plaene = [lies_plan(p) for p in sorted((BASIS / "wochenplaene").glob("KW-*.md"))]
    listen = [lies_liste(p) for p in sorted((BASIS / "einkaufslisten").glob("KW-*.md"))]
    plaene.sort(key=lambda p: p["montag"])

    daten = {
        "erzeugt": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "ziel": nw.ZIEL,
        "rezepte": [{k: r[k] for k in ("slug", "titel", "kategorien", "kueche", "mahlzeit", "sterne",
                                       "zeit", "portion", "inspiration")} for r in rezepte],
        "plaene": plaene,
        "listen": listen,
    }
    (WEB / "data.js").write_text("window.DATA = " + json.dumps(daten, ensure_ascii=False) + ";\n",
                                 encoding="utf-8")
    print(f"Web-App erzeugt: {len(rezepte)} Rezepte, {len(plaene)} Wochenpläne, {len(listen)} Einkaufslisten → web/")


if __name__ == "__main__":
    main()
