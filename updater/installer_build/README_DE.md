# Yume Companion – Setup bauen

Erzeugt `Yume-Companion-Setup-<Version>.exe` im gewählten Ausgabeordner (eine Datei, ca. 2 GB).

## Voraussetzung
Inno Setup 6 (kostenlos), z. B. `winget install JRSoftware.InnoSetup --scope user`.

## Bauen
1. Den Quellordner (dein Arbeitsordner) sauber halten (nicht starten – sonst landen Chats/Logs im Setup).
2. `build.bat` ausführen (erzeugt bei Bedarf Grafiken und `settings_de.json`, ruft dann den Compiler auf).

## Was das Setup macht
* Zielordner wählbar (Standard: `%LOCALAPPDATA%\Programs\Yume Companion`, ohne Adminrechte; Warnung bei OneDrive).
* Verknüpfungen: Startmenü + optional Desktop. Icon aus dem Rebrand-Programm (`setup_icon.ico`).
* Seite „Komponenten“: PyTorch **CUDA** (vorgewählt, wenn eine NVIDIA-GPU erkannt wird) oder **CPU**, FlashAttention-2 (nur CUDA), „jetzt installieren“, „danach starten“.
* Danach läuft `installer.bat /auto cuda|cpu [flash]` ohne Rückfragen (Konsolenfenster), bei Erfolg startet das Programm.
* Programmsprache: deutsches Setup → deutsche Programmsprache (`settings_de.json`).
* Updates/Reparatur überschreiben `settings.json`, `api.json`, `characters.json` nie.

## Kommandozeile (Tests / unbeaufsichtigt)
`/VERYSILENT /DIR="..." /INSTALLDEPS=1 /TORCH=cuda|cpu /FLASH=0|1`
Test ohne Downloads: Umgebungsvariable `SOW_INSTALLER_DRYRUN=ok` (oder `fail`) lässt `installer.bat` nur die Argumente melden.
