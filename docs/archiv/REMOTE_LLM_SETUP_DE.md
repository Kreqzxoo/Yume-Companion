# Soul of Waifu 2.5.1 – Remote-LLM-Erweiterung

## Was wurde ergänzt?

- **Globales Ausführungsziel** unter `Options → API & Providers → Local LLM execution target`:
  - `This PC (local llama.cpp)`: bisheriges Verhalten; der lokale SoW-LLM-Server wird verwendet.
  - `Remote PC (Ollama / llama.cpp)`: Figuren, deren Conversation Method `Local LLM` ist, senden ihre Textgenerierung an den konfigurierten Remote-Endpunkt. Die lokale LLM-Laufzeit wird für diese Anfragen nicht gestartet.
- **Remote LLM** als eigener Provider für einzelne Figuren, Soul Stage und den Character Assistant.
- **URL, Modell-ID und optionaler API-Token** unter `Options → API & Providers`, Provider `Remote LLM`.
- **Test Remote LLM Connection** prüft den OpenAI-kompatiblen `/v1/models`-Endpunkt. Falls noch keine Modell-ID gespeichert ist und der Server Modell-IDs auflistet, wird die erste ID vorgeschlagen/übernommen.
- Whisper/STT, TTS, Avatar, UI und die übrigen lokalen Komponenten werden durch diese Änderung nicht auf den Remote-PC verschoben.

## Einrichtung

1. Auf dem Rechner, der die LLM-Inferenz übernehmen soll, Ollama oder den `llama.cpp`-HTTP-Server starten und den OpenAI-kompatiblen Endpunkt im vertrauenswürdigen LAN erreichbar machen.
2. In Soul of Waifu `Options → API & Providers` öffnen und beim Provider `Remote LLM` die Basis-URL eintragen:
   - Ollama: `http://<LLM-PC-IP>:11434/v1`
   - llama.cpp: `http://<LLM-PC-IP>:8080/v1`
3. Falls der Endpunkt Authentifizierung verwendet, den API-Token eintragen. Bei typischen LAN-Setups ohne Authentifizierung das Feld leer lassen.
4. `Test Remote LLM Connection` drücken. Wenn die Verbindung erfolgreich ist, die vom Server gemeldete Modell-ID verwenden. Ollama erwartet normalerweise den exakten Modellnamen/-Tag; llama.cpp akzeptiert abhängig von der Serverkonfiguration die geladene Modell-ID.
5. Für einen **globalen Wechsel bereits vorhandener Local-LLM-Figuren** den Eintrag `Remote PC (Ollama / llama.cpp)` bei `Local LLM execution target` wählen. Mit `This PC` wird wieder auf den lokalen SoW-llama.cpp-Server zurückgeschaltet.
6. Alternativ kann bei einer einzelnen Figur als `Conversation Method` direkt `Remote LLM` ausgewählt werden. Diese explizite Auswahl richtet sich nach dem Remote-Endpunkt, unabhängig vom globalen Ausführungsziel.
7. Beim Wechsel des globalen Ziels auf `Remote PC` versucht die Erweiterung, einen laufenden lokalen llama.cpp-Server zu stoppen, damit dessen GPU-Speicher wieder frei wird. Wechsle den Ausführungsweg möglichst zwischen Gesprächen, nicht mitten in einer laufenden Antwort.

## Sicherheit

Ollama- oder llama.cpp-Endpunkte sind in vielen Konfigurationen nicht durch einen Login geschützt. Den Server deshalb nicht direkt ins öffentliche Internet freigeben. Nur an das vertrauenswürdige LAN binden bzw. per Firewall auf den SoW-Host beschränken. Bei Ollama ist häufig `11434` der Standardport, bei llama.cpp in dieser Anleitung `8080`.

## Kompatibilität und Grenzen

- Erwartet wird eine **OpenAI-kompatible Chat-Completions-API** mit `/v1`. Die native Ollama-API `/api/chat` ist nicht die konfigurierte Schnittstelle.
- Tool Calling und Bildanhänge funktionieren nur, wenn das konkrete Server-/Modellpaar diese OpenAI-kompatiblen Funktionen unterstützt. Textmodelle können keine Bilder verarbeiten.
- Es gibt derzeit keinen automatischen Fallback auf lokal, wenn der Remote-Server ausfällt. In diesem Fall schlägt die jeweilige LLM-Anfrage fehl; Whisper/TTS bleiben unabhängig davon lokal.
- Der Verbindungstest kann nur die Netzwerk-/API-Antwort prüfen. Er beweist nicht, dass jede Generationseinstellung oder Tool-Aufruf-Funktion vom gewählten Modell unterstützt wird.

## Prüfungen im Entwicklungscontainer

- Python-Syntaxprüfung (`compileall`) erfolgreich.
- JSON- und YAML-Konfigurationen erfolgreich geparst.
- Basis-URL-Normalisierung für Ollama, llama.cpp, `/v1/chat/completions`, `/v1/models` und leere URL mit Stubs geprüft.
- Kein echter Ollama-/llama.cpp-Endpunkt verfügbar und das `openai`-Pythonpaket war im Entwicklungscontainer nicht installiert. Deshalb wurde kein vollständiger GUI- oder Live-LLM-Test ausgeführt.
