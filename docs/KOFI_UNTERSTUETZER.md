# Ko-fi-Stufen und Discord-Rollen für Unterstützer

Diese Anleitung hilft dir, auf [Ko-fi](https://ko-fi.com/kreqzxoo) Mitgliedschaftsstufen mit echtem Mehrwert anzubieten und Unterstützern automatisch Rollen im Discord zu geben.

> **GPL-3.0 beachten:** Der Quelltext bleibt für alle offen. Biete deshalb nur Zusatznutzen an (Rolle, Mitsprache, früher Zugriff, Namensnennung, eigene Inhalte), keine gesperrten Programmfunktionen. Wer eine frühe Programmversion erhält, hat Anspruch auf den zugehörigen Quelltext.

## 1. Vorschlag für die Stufen (Preise nach Wunsch)

| Stufe | Preis | Mehrwert |
| --- | --- | --- |
| ☕ **Kaffee** | 3 € / Monat | Rolle **Supporter** im Discord, Zugang zur **#supporter-lounge** (früher Einblick in neue Funktionen), Dank im Update-Beitrag |
| 💜 **Förderer** | 8 € / Monat | Alles aus „Kaffee“, Rolle **Förderer** (hervorgehoben in der Mitgliederliste), **Name in der README**, **Mitsprache bei der Planung** (Abstimmungen), frühe Test-Setups vor dem öffentlichen Release |
| 🌟 **Mitgestalter** (optional) | 20 € / Monat | Alles aus „Förderer“, ein Wunsch pro Monat, den ich bevorzugt prüfe, ein persönlicher Demo-Charakter oder Avatar-Entwurf im Jahr |
| 🎁 **Einmalige Spende** | frei | Dank im Discord, kein Abo nötig |

Ko-fi fragt bei jeder Stufe nach Titel, Preis, Beschreibung und Bild. Die Beschreibungen findest du unten zum Kopieren.

## 2. Texte zum Kopieren

**Kaffee (3 €)**
> Ein Kaffee für die Weiterentwicklung. Du bekommst die Rolle *Supporter* im Discord und Zugang zur Supporter-Lounge mit frühen Einblicken in neue Funktionen. Danke! ☕

**Förderer (8 €)**
> Du hilfst, dass Yume Companion wächst. Alles aus „Kaffee“, dazu die Rolle *Förderer*, dein Name in der README, Mitsprache bei der Planung und frühe Test-Setups vor dem öffentlichen Release. 💜

**Mitgestalter (20 €)**
> Für alle, die das Projekt richtig voranbringen wollen. Alles aus „Förderer“, ein Wunsch pro Monat, den ich bevorzugt prüfe, und ein persönlicher Demo-Charakter oder Avatar-Entwurf im Jahr. 🌟

**Willkommensnachricht für neue Unterstützer (Ko-fi → Einstellungen)**
> Danke für deine Unterstützung! 💜 Verknüpfe dein Discord-Konto in deinem Ko-fi-Profil, dann bekommst du automatisch deine Rolle. Server: https://discord.gg/5RBgNMCPKC

**English (short):**
> *Coffee* (€3): Supporter role + supporters lounge. *Förderer* (€8): + name in the README, a say in planning, early test builds. *Mitgestalter* (€20): + a monthly request I look at first and a personal demo character or avatar sketch per year.

## 3. Discord vorbereiten (mit dem Setup-Bot)

Der mitgelieferte Discord-Setup-Bot (`yume-discord-setup`) kennt jetzt:

* die Rollen **Supporter** und **Förderer** (hervorgehoben, farblich abgesetzt),
* den privaten Kanal **💜│supporter-lounge**, den nur Supporter, Förderer und das Team sehen,
* die Antwort in den FAQ („Wie bekomme ich die Supporter-Rolle?“) mit dem Ko-fi-Link.

So wendest du es an: Panel des Bots öffnen → **Server prüfen** → **Server einrichten**. Der Bot legt die neuen Rollen und den Kanal an, ohne Bestehendes zu löschen.

## 4. Ko-fi mit Discord verknüpfen (Rollen automatisch)

Ko-fi bietet eine eigene Discord-Anbindung, die Rollen nach Stufe vergibt. Die Oberfläche kann sich ändern; sinngemäß gehst du so vor:

1. Auf Ko-fi: **Einstellungen → Integrationen (Integrations) → Discord**.
2. **Mit Discord verbinden** und deinen Server wählen. Ko-fi fügt einen eigenen Bot hinzu und fragt nach den Rechten.
3. Jeder Stufe eine **Rolle** zuordnen: *Kaffee → Supporter*, *Förderer* und *Mitgestalter → Förderer*.
4. In Discord: **Servereinstellungen → Rollen**. Ziehe die Rolle des **Ko-fi-Bots oberhalb** von *Supporter* und *Förderer*, sonst darf er sie nicht vergeben.
5. Unterstützer verknüpfen in ihrem Ko-fi-Profil ihr Discord-Konto und bekommen die Rolle automatisch.

Probiere es einmal mit einem eigenen Test-Abo oder einer Spende, bevor du es ankündigst.

## 5. Weitere Einnahmequellen mit Mehrwert

* **Ko-fi-Shop:** selbst erstellte Charakter-Pakete (`.png`-Karten), Hintergründe, Avatare (VRM, Live2D) oder Stimmen. Nur eigene Inhalte verkaufen, nichts mit fremden Rechten (Apple-Emoji, Mixamo-Dateien, Charaktere aus Anime oder Spielen).
* **Auftragsarbeiten (Commissions):** persönliche Charaktere oder Einrichtung gegen Bezahlung.
* **GitHub Sponsors** zusätzlich (niedrige Gebühren, Knopf auf der Repo-Seite). Dann in `.github/FUNDING.yml` die Zeile `github: Kreqzxoo` ergänzen.

## 6. Steuern und Recht (Deutschland)

Regelmäßige Einnahmen können steuerpflichtig oder gewerblich sein. Kläre mit dem Finanzamt oder einer Beratungsstelle, ob eine Gewerbeanmeldung oder die Kleinunternehmerregelung nötig ist. Das ist keine Rechtsberatung.
