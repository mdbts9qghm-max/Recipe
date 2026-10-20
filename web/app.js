(function () {
  "use strict";
  var D = window.DATA;
  var app = document.getElementById("app");
  var WOCHENTAGE = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];
  var KATEGORIEN = ["High Protein", "Schnelle Rezepte", "Meal Prep", "Kalorienarm", "Frühstück & Snacks"];

  // Browser-Speicher nur für Komfort (Filter, Haken); alles funktioniert auch ohne.
  function lies(k, std) {
    try { var v = localStorage.getItem(k); return v === null ? std : JSON.parse(v); } catch (e) { return std; }
  }
  function schreib(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function zahl(x) { return Math.round(x); }
  function sterne(n) { return n ? "★★★★★".slice(0, n) + "☆☆☆☆☆".slice(0, 5 - n) : ""; }
  function isoDatum(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function plusTage(iso, n) {
    var t = iso.split("-").map(Number);
    var d = new Date(t[0], t[1] - 1, t[2] + n);
    return isoDatum(d);
  }

  function makroChips(p) {
    return '<div class="makros"><span>' + zahl(p.kcal) + " kcal</span><span>" + zahl(p.protein) +
      " g P</span><span>" + zahl(p.fett) + " g F</span><span>" + zahl(p.kh) + " g KH</span></div>";
  }

  function aktuellerPlan() {
    var heute = isoDatum(new Date());
    var plan = null;
    D.plaene.forEach(function (p) {
      if (p.montag <= heute && heute <= plusTage(p.montag, 6)) plan = p;
    });
    return plan;
  }

  // ---------------------------------------------------------------- Heute
  function heute() {
    var jetzt = new Date();
    var tag = WOCHENTAGE[jetzt.getDay()];
    var html = '<div class="tageskopf"><h1>Heute</h1><span class="meta">' + tag + ", " +
      jetzt.toLocaleDateString("de-DE", { day: "numeric", month: "long" }) + "</span></div>";
    var plan = aktuellerPlan();
    if (!plan) {
      var naechster = D.plaene.filter(function (p) { return p.montag > isoDatum(jetzt); })[0];
      html += '<div class="karte leer">Für diese Woche gibt es noch keinen Wochenplan.<br>' +
        "Sag im Chat einfach <strong>„Woche planen“</strong>." +
        (naechster ? '<br><br><a href="#woche">Nächster Plan: ' + esc(naechster.titel) + "</a>" : "") + "</div>";
      html += '<h2>Ideen aus dem Rezeptbuch</h2>' + vorschlaege();
      app.innerHTML = html;
      return;
    }
    var mahlzeiten = plan.tage[tag] || {};
    ["Frühstück", "Mittag", "Abend"].forEach(function (m) {
      html += '<div class="karte mahlzeit"><div class="label">' + m + '</div><div class="inhalt">' +
        (mahlzeiten[m] || '<span class="meta">nicht geplant</span>') + "</div></div>";
    });
    if (plan.summen[tag]) html += '<div class="karte"><div class="label">Tagessumme</div><div class="inhalt">' + plan.summen[tag] + "</div></div>";
    html += '<p class="meta"><a href="#woche">Ganzer Wochenplan ' + esc(plan.titel) + " ›</a></p>";
    app.innerHTML = html;
  }

  function vorschlaege() {
    // Je ein Frühstück und zwei Hauptgerichte, täglich wechselnd
    var tagNr = Math.floor(Date.now() / 86400000);
    function waehle(liste, n) { return liste[(tagNr * 7 + n * 3) % liste.length]; }
    var fr = D.rezepte.filter(function (r) { return /Frühstück/.test(r.mahlzeit); });
    var haupt = D.rezepte.filter(function (r) { return /Mittag|Abend/.test(r.mahlzeit); });
    return [waehle(fr, 0), waehle(haupt, 1), waehle(haupt, 2)].map(rezeptKarte).join("");
  }

  // ---------------------------------------------------------------- Rezepte
  function rezeptKarte(r) {
    return '<a class="karte" href="r/' + r.slug + '.html"><div class="titel">' + esc(r.titel) +
      (r.sterne ? ' <span class="meta">' + sterne(r.sterne) + "</span>" : "") + '</div><div class="unter">' +
      esc(r.kueche) + " · " + (r.zeit.gesamt || "?") + " min · " + esc(r.mahlzeit) + "</div>" + makroChips(r.portion) + "</a>";
  }

  var filter = lies("filter", { suche: "", kategorie: "", kueche: "", sterne: "" });

  function rezepte() {
    var kuechen = [];
    D.rezepte.forEach(function (r) { if (kuechen.indexOf(r.kueche) < 0) kuechen.push(r.kueche); });
    kuechen.sort();
    function zeile(name, werte, labels) {
      return '<div class="filterzeile" data-filter="' + name + '">' + werte.map(function (w, i) {
        return '<button data-wert="' + esc(w) + '" class="' + (filter[name] === w ? "an" : "") + '">' + esc(labels ? labels[i] : w || "Alle") + "</button>";
      }).join("") + "</div>";
    }
    app.innerHTML = "<h1>Rezeptbuch</h1>" +
      '<input class="suche" type="search" placeholder="Suchen, z. B. Hähnchen, Skyr, Pasta" value="' + esc(filter.suche) + '">' +
      zeile("kategorie", [""].concat(KATEGORIEN)) +
      zeile("kueche", [""].concat(kuechen), ["Alle Küchen"].concat(kuechen)) +
      zeile("sterne", ["", "4", "3", "0"], ["Alle Bewertungen", "ab ★★★★", "ab ★★★", "unbewertet"]) +
      '<div id="liste"></div>';
    app.querySelector(".suche").addEventListener("input", function (e) { filter.suche = e.target.value; liste(); });
    app.querySelectorAll(".filterzeile").forEach(function (z) {
      z.addEventListener("click", function (e) {
        var b = e.target.closest("button");
        if (!b) return;
        filter[z.dataset.filter] = filter[z.dataset.filter] === b.dataset.wert ? "" : b.dataset.wert;
        z.querySelectorAll("button").forEach(function (x) { x.classList.toggle("an", filter[z.dataset.filter] === x.dataset.wert && x.dataset.wert !== ""); });
        liste();
      });
    });
    liste();
  }

  function liste() {
    schreib("filter", filter);
    var q = filter.suche.trim().toLowerCase();
    var treffer = D.rezepte.filter(function (r) {
      if (filter.kategorie && r.kategorien.indexOf(filter.kategorie) < 0) return false;
      if (filter.kueche && r.kueche !== filter.kueche) return false;
      if (filter.sterne === "0" && r.sterne) return false;
      if (filter.sterne && filter.sterne !== "0" && !(r.sterne >= Number(filter.sterne))) return false;
      if (r.sterne && r.sterne <= 2 && filter.sterne !== "0") return false; // aussortiert
      if (q) {
        var text = (r.titel + " " + r.kueche + " " + r.kategorien.join(" ") + " " + (r.inspiration || "")).toLowerCase();
        return q.split(/\s+/).every(function (w) { return text.indexOf(w) >= 0; });
      }
      return true;
    });
    document.getElementById("liste").innerHTML = '<p class="anzahl">' + treffer.length + " von " + D.rezepte.length +
      " Rezepten</p>" + (treffer.length ? treffer.map(rezeptKarte).join("") : '<div class="leer">Keine Treffer.</div>');
  }

  // ---------------------------------------------------------------- Woche & Einkauf
  function auswahl(liste, schluessel, std) {
    if (!liste.length) return null;
    var gewaehlt = lies(schluessel, std);
    var eintrag = liste.filter(function (x) { return x.name === gewaehlt; })[0] || liste[liste.length - 1];
    return eintrag;
  }

  function auswahlFeld(liste, aktiv, schluessel) {
    if (liste.length < 2) return "";
    return '<select class="auswahl" data-schluessel="' + schluessel + '">' + liste.map(function (x) {
      return '<option value="' + esc(x.name) + '"' + (x.name === aktiv.name ? " selected" : "") + ">" + esc(x.titel) + "</option>";
    }).join("") + "</select>";
  }

  function auswahlBinden(neuZeichnen) {
    var s = app.querySelector(".auswahl");
    if (s) s.addEventListener("change", function () { schreib(s.dataset.schluessel, s.value); neuZeichnen(); });
  }

  function woche() {
    var plan = auswahl(D.plaene, "plan", (aktuellerPlan() || {}).name);
    if (!plan) {
      app.innerHTML = '<h1>Wochenplan</h1><div class="karte leer">Noch kein Wochenplan vorhanden.<br>Sag im Chat <strong>„Woche planen“</strong>.</div>';
      return;
    }
    app.innerHTML = "<h1>Wochenplan</h1>" + auswahlFeld(D.plaene, plan, "plan") + '<div class="inhalt">' + plan.html + "</div>";
    auswahlBinden(woche);
  }

  function einkauf() {
    var liste = auswahl(D.listen, "liste", null);
    if (!liste) {
      app.innerHTML = '<h1>Einkaufsliste</h1><div class="karte leer">Noch keine Einkaufsliste vorhanden.<br>Sie entsteht automatisch mit dem Wochenplan.</div>';
      return;
    }
    var haken = lies("haken:" + liste.name, {});
    app.innerHTML = "<h1>Einkaufsliste</h1>" + auswahlFeld(D.listen, liste, "liste") +
      '<p><button class="klein-knopf" id="zuruecksetzen">Alle Haken entfernen</button></p>' +
      '<div class="inhalt">' + liste.html + "</div>";
    app.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      if (cb.dataset.id in haken) cb.checked = haken[cb.dataset.id];
      cb.addEventListener("change", function () { haken[cb.dataset.id] = cb.checked; schreib("haken:" + liste.name, haken); });
    });
    document.getElementById("zuruecksetzen").addEventListener("click", function () {
      haken = {};
      app.querySelectorAll("input[type=checkbox]").forEach(function (cb) { cb.checked = false; haken[cb.dataset.id] = false; });
      schreib("haken:" + liste.name, haken);
    });
    auswahlBinden(einkauf);
  }

  // ---------------------------------------------------------------- Router
  var SEITEN = { heute: heute, rezepte: rezepte, woche: woche, einkauf: einkauf };
  function route() {
    var tab = location.hash.replace("#", "") || "heute";
    if (!SEITEN[tab]) tab = "heute";
    document.querySelectorAll(".tabs a").forEach(function (a) { a.classList.toggle("aktiv", a.dataset.tab === tab); });
    SEITEN[tab]();
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);
  route();
})();
