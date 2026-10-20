(function () {
  "use strict";
  var schritte = window.KOCHSCHRITTE || [];
  var box = document.getElementById("kochmodus");
  var nr = 0;
  var sperre = null;

  function zeige() {
    var s = schritte[nr];
    document.getElementById("km-zaehler").textContent = "Schritt " + (nr + 1) + " von " + schritte.length;
    document.getElementById("km-teil").textContent = s.teil;
    document.getElementById("km-text").innerHTML = s.html;
    document.getElementById("km-zurueck").disabled = nr === 0;
    document.getElementById("km-weiter").textContent = nr === schritte.length - 1 ? "Fertig ✓" : "Weiter ›";
  }

  // Bildschirm anlassen (Screen Wake Lock, ab iOS 16.4)
  function wachHalten() {
    var hinweis = document.getElementById("km-wach");
    if (!("wakeLock" in navigator)) { hinweis.textContent = "Tipp: Automatische Sperre in den Einstellungen kurz verlängern."; return; }
    navigator.wakeLock.request("screen").then(function (s) {
      sperre = s;
      hinweis.textContent = "Bildschirm bleibt an";
    }).catch(function () { hinweis.textContent = ""; });
  }
  function freigeben() { if (sperre) { sperre.release(); sperre = null; } }
  document.addEventListener("visibilitychange", function () {
    if (!box.hidden && document.visibilityState === "visible") wachHalten();
  });

  function starten() {
    if (!schritte.length) return;
    nr = 0;
    box.hidden = false;
    document.body.style.overflow = "hidden";
    zeige();
    wachHalten();
  }
  function beenden() {
    box.hidden = true;
    document.body.style.overflow = "";
    freigeben();
  }
  function weiter() { if (nr < schritte.length - 1) { nr++; zeige(); } else beenden(); }
  function zurueck() { if (nr > 0) { nr--; zeige(); } }

  document.getElementById("kochmodus-start").addEventListener("click", starten);
  document.getElementById("km-schliessen").addEventListener("click", beenden);
  document.getElementById("km-weiter").addEventListener("click", weiter);
  document.getElementById("km-zurueck").addEventListener("click", zurueck);

  // Wischen: links = weiter, rechts = zurück
  var startX = null;
  box.addEventListener("touchstart", function (e) { startX = e.touches[0].clientX; }, { passive: true });
  box.addEventListener("touchend", function (e) {
    if (startX === null) return;
    var dx = e.changedTouches[0].clientX - startX;
    if (Math.abs(dx) > 60) (dx < 0 ? weiter : zurueck)();
    startX = null;
  });

  // Zutatenliste für MacroFactor kopieren
  function toast(text) {
    var t = document.createElement("div");
    t.className = "toast";
    t.textContent = text;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 2200);
  }
  document.getElementById("macrofactor").addEventListener("click", function () {
    var text = document.getElementById("macrofactor-text").value;
    function altKopieren() {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); toast("Zutaten kopiert"); } catch (e) { toast("Kopieren nicht möglich"); }
      ta.remove();
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast("Zutaten kopiert"); }, altKopieren);
    } else {
      altKopieren();
    }
  });
})();
