#!/usr/bin/env python3
"""Nährwertrechner für das Rezeptbuch.

Alle Werte in zutaten.csv gelten pro 100 g Rohgewicht. Rezepte sind für
2 Portionen geschrieben; "pro Portion" = Summe / 2.

Befehle:
  python3 naehrwerte.py rechne zutat=gramm [zutat=gramm ...]
      Nährwerte für eine Zutatenliste ausgeben (Markdown-Blöcke zum Einfügen).

  python3 naehrwerte.py rezept DATEI [--schreiben]
      Liest die Tabelle unter "## Nährwert-Berechnung" (Spalte 1 = Schlüssel aus
      zutaten.csv, Spalte 2 = Menge in g) und rechnet neu. Mit --schreiben werden
      der Abschnitt "## Nährwerte pro Portion" und die Berechnungstabelle im
      Rezept aktualisiert.

  python3 naehrwerte.py pruefen [DATEI|ORDNER ...]
      Prüft alle Rezepte: Rechnung aktuell, Plausibilität (±5 %),
      Kategorien passend zu den Kriterien.

  python3 naehrwerte.py inhaltsverzeichnis
      Erzeugt rezeptbuch.md aus allen Rezepten neu.

  python3 naehrwerte.py csv-check
      Prüft jede Zeile in zutaten.csv auf Plausibilität.
"""

import csv
import re
import sys
from pathlib import Path

BASIS = Path(__file__).resolve().parent
CSV_DATEI = BASIS / "zutaten.csv"
REZEPT_ORDNER = BASIS / "rezepte"
REZEPTBUCH = BASIS / "rezeptbuch.md"

PORTIONEN = 2
NAEHRSTOFFE = ["kcal", "protein", "fett", "gesaettigt", "kh", "zucker", "ballaststoffe", "salz"]
ZIEL = {"kcal": 2275, "protein": 149, "fett": 101, "kh": 191}

# Reihenfolge der Hauptkategorien (= Ordner) im Inhaltsverzeichnis
ORDNER = [
    ("fruehstueck-snacks", "Frühstück & Snacks"),
    ("high-protein", "High Protein"),
    ("schnell", "Schnelle Rezepte"),
    ("meal-prep", "Meal Prep"),
    ("kalorienarm", "Kalorienarm"),
]


# ---------------------------------------------------------------- Daten

def lade_zutaten():
    with open(CSV_DATEI, newline="", encoding="utf-8") as f:
        return {
            zeile["zutat"].strip(): {n: float(zeile[n]) for n in NAEHRSTOFFE}
            for zeile in csv.DictReader(f)
        }


def berechne(posten, db):
    """posten: Liste von (schluessel, gramm). Liefert (zeilen, summe, portion)."""
    fehlend = [k for k, _ in posten if k not in db]
    if fehlend:
        raise SystemExit(f"Unbekannte Zutat(en), bitte in zutaten.csv eintragen: {', '.join(fehlend)}")
    zeilen = []
    summe = dict.fromkeys(NAEHRSTOFFE, 0.0)
    for schluessel, gramm in posten:
        werte = {n: db[schluessel][n] * gramm / 100 for n in NAEHRSTOFFE}
        zeilen.append((schluessel, gramm, werte))
        for n in NAEHRSTOFFE:
            summe[n] += werte[n]
    portion = {n: summe[n] / PORTIONEN for n in NAEHRSTOFFE}
    return zeilen, summe, portion


def plausibilitaet(w):
    """Atwater-Check: P×4 + KH×4 + F×9 innerhalb ±5 % der kcal.
    Zusätzlich die EU-Rechnung inkl. Ballaststoffe×2 (Etiketten zählen sie mit)."""
    if w["kcal"] == 0:
        return True, 0.0, 0.0
    basis = w["protein"] * 4 + w["kh"] * 4 + w["fett"] * 9
    abw = (basis - w["kcal"]) / w["kcal"] * 100
    abw_eu = (basis + w["ballaststoffe"] * 2 - w["kcal"]) / w["kcal"] * 100
    return abs(abw) <= 5 or abs(abw_eu) <= 5, abw, abw_eu


# ---------------------------------------------------------------- Formatierung

def zahl(x, stellen=1):
    return f"{x:.{stellen}f}".replace(".", ",")


def g(x, stellen=1):
    return f"{zahl(x, stellen)} g"


def naehrwerte_block(p):
    ok, abw, abw_eu = plausibilitaet(p)
    p100 = p["protein"] / p["kcal"] * 100 if p["kcal"] else 0
    e_p = p["protein"] * 4
    e_f = p["fett"] * 9
    e_k = p["kh"] * 4
    e = e_p + e_f + e_k or 1
    zeilen = [
        "| kcal | Protein | Fett | davon gesättigt | Kohlenhydrate | davon Zucker | Ballaststoffe | Salz |",
        "|---|---|---|---|---|---|---|---|",
        f"| {p['kcal']:.0f} | {g(p['protein'])} | {g(p['fett'])} | {g(p['gesaettigt'])} | {g(p['kh'])} "
        f"| {g(p['zucker'])} | {g(p['ballaststoffe'])} | {g(p['salz'], 2)} |",
        "",
        f"- Anteil am Tagesziel: {p['kcal'] / ZIEL['kcal'] * 100:.0f} % kcal · "
        f"{p['protein'] / ZIEL['protein'] * 100:.0f} % Protein · "
        f"{p['fett'] / ZIEL['fett'] * 100:.0f} % Fett · {p['kh'] / ZIEL['kh'] * 100:.0f} % KH",
        f"- Protein pro 100 kcal: {g(p100)}",
        f"- Makroverteilung: {e_p / e * 100:.0f} % Protein / {e_f / e * 100:.0f} % Fett / {e_k / e * 100:.0f} % KH",
    ]
    return "\n".join(zeilen)


def berechnung_tabelle(zeilen, summe, portion):
    out = [
        "| Zutat (zutaten.csv) | Menge | kcal | Protein | Fett | KH |",
        "|---|---|---|---|---|---|",
    ]
    for schluessel, gramm, w in zeilen:
        out.append(f"| {schluessel} | {zahl(gramm, 0 if gramm == int(gramm) else 1)} g | {w['kcal']:.0f} | {zahl(w['protein'])} "
                   f"| {zahl(w['fett'])} | {zahl(w['kh'])} |")
    out.append(f"| **Summe (2 Portionen)** | | **{summe['kcal']:.0f}** | **{zahl(summe['protein'])}** "
               f"| **{zahl(summe['fett'])}** | **{zahl(summe['kh'])}** |")
    out.append(f"| **pro Portion** | | **{portion['kcal']:.0f}** | **{zahl(portion['protein'])}** "
               f"| **{zahl(portion['fett'])}** | **{zahl(portion['kh'])}** |")
    ok, abw, abw_eu = plausibilitaet(portion)
    out.append("")
    out.append(f"Plausibilitätscheck (P×4 + KH×4 + F×9): {zahl(abw)} % Abweichung"
               + (f", inkl. Ballaststoffe×2: {zahl(abw_eu)} %" if abs(abw) > 5 else "")
               + (" → bestanden." if ok else " → NICHT bestanden!"))
    out.append("Berechnet mit `naehrwerte.py` aus Rohgewichten; Werte sind Schätzungen "
               "(Bundeslebensmittelschlüssel, USDA, Herstellerangaben).")
    return "\n".join(out)


# ---------------------------------------------------------------- Rezept-Dateien

def abschnitt(text, titel):
    """Gibt (start, ende) des Inhalts unter '## titel' bis zur nächsten '## '-Überschrift zurück."""
    m = re.search(rf"^## {re.escape(titel)}[^\n]*\n", text, re.M)
    if not m:
        return None
    n = re.search(r"^## ", text[m.end():], re.M)
    ende = m.end() + n.start() if n else len(text)
    return m.end(), ende


def lies_posten(text):
    bereich = abschnitt(text, "Nährwert-Berechnung")
    if not bereich:
        raise SystemExit("Abschnitt '## Nährwert-Berechnung' fehlt.")
    posten = []
    for zeile in text[bereich[0]:bereich[1]].splitlines():
        zellen = [z.strip() for z in zeile.strip().strip("|").split("|")]
        if len(zellen) < 2 or zellen[0].startswith(("Zutat", "---", "**")) or not zeile.strip().startswith("|"):
            continue
        schluessel = zellen[0].strip("` ")
        m = re.match(r"([\d.,]+)\s*(g|ml)?", zellen[1])
        if not m:
            raise SystemExit(f"Menge nicht lesbar: {zeile}")
        posten.append((schluessel, float(m.group(1).replace(",", "."))))
    return posten


def kopf(text, feld):
    m = re.search(rf"^\*\*{re.escape(feld)}:\*\*\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def gesamtzeit(text):
    m = re.search(r"Gesamt\s*(?:ca\.\s*)?(\d+)\s*min", kopf(text, "Zeit"))
    return int(m.group(1)) if m else None


def rezept_info(pfad, db):
    text = pfad.read_text(encoding="utf-8")
    _, _, portion = berechne(lies_posten(text), db)
    titel = re.search(r"^# (.+)$", text, re.M).group(1).strip()
    bewertung = kopf(text, "Bewertung")
    sterne = re.search(r"(\d)\s*/\s*5", bewertung)
    return {
        "pfad": pfad,
        "text": text,
        "titel": titel,
        "kategorien": [k.strip() for k in kopf(text, "Kategorien").split("·") if k.strip()],
        "kueche": kopf(text, "Küche"),
        "mahlzeit": kopf(text, "Mahlzeit"),
        "inspiration": kopf(text, "Inspiration"),
        "sterne": int(sterne.group(1)) if sterne else None,
        "zeit": gesamtzeit(text),
        "portion": portion,
    }


def schreibe_rezept(pfad, db):
    text = pfad.read_text(encoding="utf-8")
    zeilen, summe, portion = berechne(lies_posten(text), db)
    for titel, inhalt in (("Nährwert-Berechnung", berechnung_tabelle(zeilen, summe, portion)),
                          ("Nährwerte pro Portion", naehrwerte_block(portion))):
        start, ende = abschnitt(text, titel)
        text = text[:start] + "\n" + inhalt + "\n\n" + text[ende:].lstrip("\n")
    pfad.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    return portion


def erwartete_kategorien(info):
    p = info["portion"]
    mahlzeit = info["mahlzeit"].lower()
    erwartet = {}
    erwartet["High Protein"] = p["protein"] >= 40 or p["protein"] / p["kcal"] * 100 >= 10
    if info["zeit"] is not None:
        erwartet["Schnelle Rezepte"] = info["zeit"] <= 25
    hauptmahlzeit = "mittag" in mahlzeit or "abend" in mahlzeit
    erwartet["Kalorienarm"] = hauptmahlzeit and p["kcal"] <= 550 and p["protein"] >= 35
    erwartet["Frühstück & Snacks"] = "frühstück" in mahlzeit or "snack" in mahlzeit
    return erwartet


def alle_rezepte(pfade=None):
    if not pfade:
        pfade = [REZEPT_ORDNER]
    dateien = []
    for p in map(Path, pfade):
        dateien += sorted(p.rglob("*.md")) if p.is_dir() else [p]
    return dateien


# ---------------------------------------------------------------- Befehle

def cmd_rechne(args, db):
    posten = []
    for a in args:
        k, _, v = a.partition("=")
        posten.append((k.strip(), float(v.replace(",", ".").rstrip("gml "))))
    zeilen, summe, portion = berechne(posten, db)
    print("## Nährwerte pro Portion\n")
    print(naehrwerte_block(portion))
    print("\n## Nährwert-Berechnung\n")
    print(berechnung_tabelle(zeilen, summe, portion))


def cmd_rezept(args, db):
    pfad = Path(args[0])
    if "--schreiben" in args:
        p = schreibe_rezept(pfad, db)
        print(f"{pfad}: aktualisiert – {p['kcal']:.0f} kcal · {zahl(p['protein'])} g P · "
              f"{zahl(p['fett'])} g F · {zahl(p['kh'])} g KH pro Portion")
    else:
        zeilen, summe, portion = berechne(lies_posten(pfad.read_text(encoding="utf-8")), db)
        print(naehrwerte_block(portion))
        print()
        print(berechnung_tabelle(zeilen, summe, portion))


def cmd_pruefen(args, db):
    fehler = 0
    for pfad in alle_rezepte(args):
        info = rezept_info(pfad, db)
        p = info["portion"]
        meldungen = []
        ok, abw, abw_eu = plausibilitaet(p)
        if not ok:
            meldungen.append(f"Plausibilität verfehlt ({zahl(abw)} %)")
        # Steht im Kopf der aktuelle Wert?
        start, ende = abschnitt(info["text"], "Nährwerte pro Portion")
        if naehrwerte_block(p) not in info["text"][start:ende]:
            meldungen.append("Nährwerte veraltet → `rezept DATEI --schreiben` ausführen")
        for kat, soll in erwartete_kategorien(info).items():
            ist = kat in info["kategorien"]
            if soll and not ist:
                meldungen.append(f"Kategorie fehlt: {kat}")
            if ist and not soll:
                meldungen.append(f"Kategorie passt nicht: {kat}")
        status = "OK " if not meldungen else "!! "
        fehler += bool(meldungen)
        print(f"{status}{pfad.relative_to(BASIS)}: {p['kcal']:.0f} kcal · {zahl(p['protein'])} g P · "
              f"{zahl(p['fett'])} g F · {zahl(p['kh'])} g KH · {info['zeit']} min")
        for m in meldungen:
            print(f"     - {m}")
    print(f"\n{fehler} Rezept(e) mit Hinweisen.")
    return 1 if fehler else 0


def cmd_inhaltsverzeichnis(db):
    infos = [rezept_info(p, db) for p in alle_rezepte()]
    out = [
        "# Rezeptbuch",
        "",
        f"**{len(infos)} Rezepte** · Nährwerte pro Portion (= meine Portion) · "
        "automatisch erzeugt mit `python3 naehrwerte.py inhaltsverzeichnis`",
        "",
    ]
    for ordner, name in ORDNER:
        gruppe = [i for i in infos if i["pfad"].parent.name == ordner]
        if not gruppe:
            continue
        gruppe.sort(key=lambda i: i["titel"])
        out += [f"## {name} ({len(gruppe)})", "",
                "| Rezept | Kategorien | Küche | Bewertung | Zeit | kcal | Protein | Fett | KH |",
                "|---|---|---|---|---|---|---|---|---|"]
        for i in gruppe:
            p = i["portion"]
            if i["sterne"] is None:
                bew = "–"
            elif i["sterne"] <= 2:
                bew = f"{'★' * i['sterne']} aussortiert"
            else:
                bew = "★" * i["sterne"]
            link = i["pfad"].relative_to(BASIS).as_posix()
            out.append(f"| [{i['titel']}]({link}) | {' · '.join(i['kategorien'])} | {i['kueche']} | {bew} "
                       f"| {i['zeit']} min | {p['kcal']:.0f} | {p['protein']:.0f} g | {p['fett']:.0f} g "
                       f"| {p['kh']:.0f} g |")
        out.append("")

    # Übersicht nach Kategorie und Küche
    kategorien = {}
    kuechen = {}
    for i in infos:
        for k in i["kategorien"]:
            kategorien[k] = kategorien.get(k, 0) + 1
        kuechen[i["kueche"]] = kuechen.get(i["kueche"], 0) + 1
    out += ["## Übersicht", "", "| Kategorie | Anzahl |", "|---|---|"]
    out += [f"| {k} | {n} |" for k, n in sorted(kategorien.items())]
    out += ["", "| Küche | Anzahl |", "|---|---|"]
    out += [f"| {k} | {n} |" for k, n in sorted(kuechen.items())]
    REZEPTBUCH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"rezeptbuch.md mit {len(infos)} Rezepten geschrieben.")


def cmd_csv_check(db):
    for name, w in db.items():
        ok, abw, abw_eu = plausibilitaet(w)
        if not ok:
            print(f"{name}: {zahl(abw)} % (inkl. Ballaststoffe {zahl(abw_eu)} %)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    db = lade_zutaten()
    befehl, args = sys.argv[1], sys.argv[2:]
    if befehl == "rechne":
        cmd_rechne(args, db)
    elif befehl == "rezept":
        cmd_rezept(args, db)
    elif befehl == "pruefen":
        return cmd_pruefen(args, db)
    elif befehl == "inhaltsverzeichnis":
        cmd_inhaltsverzeichnis(db)
    elif befehl == "csv-check":
        cmd_csv_check(db)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
