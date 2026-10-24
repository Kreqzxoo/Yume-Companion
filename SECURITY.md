# Sicherheit

## Schwachstellen melden

Bitte **nicht** als öffentliches Issue. Nutze auf GitHub *Security → Report a vulnerability* (privater Bericht) oder schreibe die Betreuerin / den Betreuer des Repositories direkt an. Nenne Version, betroffene Funktion und Schritte zum Nachstellen. Ohne Gewähr auf feste Antwortzeiten (Hobbyprojekt).

## Was geschützt ist

* Webserver (Port 8000) und Dashboard (Port 8765) verlangen einen Token. Dashboard ist standardmäßig nur lokal erreichbar.
* Handys koppeln per Einmal-Code und bekommen einen eigenen, widerrufbaren Schlüssel.
* Werkzeuge mit Wirkung (Programme, Skripte, Handy, Smart Home) verlangen Bestätigung oder Freigabe.
* Organizer-Passwörter sind mit der Windows-Datenschutz-Funktion verschlüsselt.

## Was du selbst beachten musst

* Gib den Webserver, das Dashboard und den LLM-Server **nicht** ohne Tunnel/VPN ins Internet.
* Teile keine Dateien aus `app\configuration`, keine Backups und keine Protokolle ungeprüft.
* Nutze für Mail ein **App-Passwort** und für Cloud-Dienste eigene Schlüssel, die du bei Verdacht sofort erneuerst.

Mehr: [docs/14-backup-updates-sicherheit.md](docs/14-backup-updates-sicherheit.md).
