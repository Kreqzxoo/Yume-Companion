"""Turns technical LLM / network errors into a short sentence that says what is wrong and what to do (German)."""
from __future__ import annotations

import re


def llm_error(text: str, base_url: str = "") -> str:
    raw = str(text or "")
    low = raw.lower()
    where = f" ({base_url})" if base_url else ""
    if "exceed_context" in low or "exceeds the available context" in low or "context length" in low or "maximum context" in low:
        n = re.search(r"n_ctx['\"]?\s*[:=]\s*(\d+)", raw)
        size = f" (aktuell {n.group(1)} Tokens)" if n else ""
        return (f"Der Kontext des LLM-Servers ist zu klein{size}. Stelle im Yume LLM Server den Kontext auf 16384 und starte den Server neu "
                f"(oder verkürze den Chat / den Charakter-Prompt).")
    if any(k in low for k in ("connection refused", "connecterror", "connect call failed", "all connection attempts failed", "name or service",
                              "getaddrinfo", "no route to host", "network is unreachable", "connection error", "timed out", "timeout", "remoteprotocolerror")):
        return f"Der LLM-Server ist nicht erreichbar{where}. Läuft er, und stimmen Adresse und Port? Prüfe auch die Firewall."
    if "401" in low or "invalid api key" in low or "incorrect api key" in low or "unauthorized" in low:
        return "Der API-Schlüssel / Token wurde abgelehnt (401). Prüfe den Eintrag unter Einstellungen > Sprachmodell & APIs."
    if "403" in low or "forbidden" in low or "permission" in low:
        return "Der Zugriff wurde verweigert (403). Prüfe Token und Rechte des Servers."
    if "429" in low or "rate limit" in low or "quota" in low:
        return "Das Limit des Anbieters ist erreicht (zu viele Anfragen oder Guthaben leer). Warte kurz oder prüfe dein Konto."
    if "out of memory" in low or "cuda error" in low:
        return "Dem Modell fehlt Grafikspeicher. Nimm ein kleineres Modell oder weniger Kontext / GPU-Layer."
    if "loading model" in low or "503" in low or "unavailable" in low:
        return "Das Modell wird noch geladen oder der Server ist überlastet. Warte einen Moment und versuche es erneut."
    if "404" in low or "model_not_found" in low or "does not exist" in low or "not found" in low:
        return "Modell oder Adresse nicht gefunden (404). Prüfe den Modellnamen und die Server-Adresse in den Einstellungen."
    if "400" in low or "bad request" in low:
        return "Der Server hat die Anfrage abgelehnt (400): " + re.sub(r"\s+", " ", raw)[:160]
    return re.sub(r"\s+", " ", raw)[:220]
