// Passwortschutz für die Web-App auf Vercel (HTTP Basic Auth).
// Das Passwort steht in der Vercel-Umgebungsvariable APP_PASSWORT, nicht im Repo.
// Benutzername ist egal, nur das Passwort zählt.

export const config = { matcher: "/:path*" };

export default function middleware(request) {
  const passwort = process.env.APP_PASSWORT;
  if (!passwort) {
    return new Response("APP_PASSWORT ist in den Vercel-Einstellungen nicht gesetzt.", { status: 500 });
  }
  const kopf = request.headers.get("authorization") || "";
  if (kopf.startsWith("Basic ")) {
    let zugang = "";
    try { zugang = atob(kopf.slice(6)); } catch (e) { zugang = ""; }
    const eingabe = zugang.slice(zugang.indexOf(":") + 1);
    if (zugang.includes(":") && eingabe === passwort) return; // ohne Antwort geht die Anfrage normal weiter
  }
  return new Response("Anmeldung erforderlich", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Rezeptbuch", charset="UTF-8"' },
  });
}
