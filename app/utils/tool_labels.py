"""Short German status texts for tool calls: shown live on the phone ("Öffne Spotify …" -> "✓ Spotify geöffnet")."""
from __future__ import annotations

import json


def _s(value, limit: int = 40) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def running_label(tool: str, args: dict) -> str:
    a = args if isinstance(args, dict) else {}
    action = str(a.get("action", "")).lower()
    if tool == "spotify":
        q = _s(a.get("query"))
        return {
            "play": f"Suche und spiele „{q}“ …", "search": f"Suche „{q}“ bei Spotify …", "pause": "Pausiere die Musik …",
            "resume": "Setze die Musik fort …", "next": "Nächster Titel …", "previous": "Voriger Titel …", "now": "Prüfe, was gerade läuft …",
            "volume": f"Stelle die Lautstärke auf {a.get('level', '?')} % …", "queue": f"Füge „{q}“ zur Warteschlange hinzu …",
            "shuffle": "Ändere die Zufallswiedergabe …", "repeat": "Ändere das Wiederholen …", "playlists": "Lade deine Playlists …",
            "play_playlist": f"Starte die Playlist „{q}“ …", "play_liked": "Starte deine gespeicherten Titel …",
            "devices": "Suche Spotify-Geräte …", "transfer": "Verschiebe die Wiedergabe …",
        }.get(action, "Spotify …")
    if tool == "phone":
        app = _s(a.get("app"))
        return {
            "open_app": f"Öffne {app} …", "list_apps": "Suche Apps …", "call": f"Rufe {_s(a.get('number'))} an …", "sms": "Sende eine SMS …",
            "open_url": "Öffne die Webseite …", "web_search": "Suche im Internet …", "set_alarm": "Stelle den Wecker …", "alarm_set": "Stelle den Wecker …",
            "alarm_list": "Lese deine Wecker …", "alarm_cancel": "Lösche den Wecker …", "set_timer": "Stelle den Timer …",
            "flashlight": "Schalte die Taschenlampe …", "volume": "Stelle die Lautstärke …", "media": "Steuere die Wiedergabe …",
            "battery": "Prüfe den Akku …", "location": "Hole deinen Standort …", "notifications": "Lese deine Benachrichtigungen …",
            "find_contact": "Suche den Kontakt …", "calendar_today": "Lese deinen Kalender …", "screen_read": "Lese den Bildschirm …",
            "screen_look": "Schaue auf den Bildschirm …", "tap": "Tippe auf dem Bildschirm …", "type": "Tippe einen Text …",
            "scroll": "Scrolle …", "back": "Gehe zurück …", "home": "Gehe zum Startbildschirm …", "camera_look": "Schaue durch die Kamera …",
            "speak": "Spreche auf dem Handy …",
        }.get(action, "Bediene das Handy …")
    return {
        "web_search": "Suche im Internet …", "calculator": "Rechne …", "get_current_datetime": "Prüfe die Uhrzeit …", "open_url": "Öffne die Webseite …",
        "media_control": "Steuere die Medien am PC …", "app_control": "Öffne ein Programm am PC …", "take_screenshot": "Mache einen Screenshot …",
        "browse_web": "Bediene den Browser …", "execute_code": "Führe Code aus …", "get_system_info": "Prüfe das System …",
    }.get(tool, f"Nutze {tool} …")


def result_text(result) -> str:
    text = result.get("result", "") if isinstance(result, dict) else str(result or "")
    if not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False)
    return _s(" ".join(text.split()), 90)
