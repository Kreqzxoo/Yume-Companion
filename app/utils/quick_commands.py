"""Quick commands without the language model.

Short, clear commands ("stopp die Musik", "nächster Song", "öffne WhatsApp", "Taschenlampe an", "lauter") are recognised by simple rules and
executed at once. The AI then only confirms the result in its own words - no tool decision, no waiting for the model. Everything that is not
clearly one of these commands still goes to the model as before.
"""
from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger("QuickCommands")

POLITE = {"bitte", "mal", "mir", "doch", "jetzt", "eben", "kannst", "könntest", "du", "würdest", "hey", "ok", "okay", "danke", "schnell", "einfach"}
MUSIC = {"musik", "spotify", "song", "songs", "lied", "titel", "track"}
PC_WORDS = {"pc", "computer", "rechner", "laptop", "desktop", "windows"}
PAUSE = {"stopp", "stoppe", "stoppen", "stop", "pause", "pausiere", "pausieren", "aus", "ausmachen", "ausschalten", "anhalten", "halt"}
RESUME = {"weiter", "weiterspielen", "fortsetzen", "an", "wieder", "anmachen", "einschalten"}
NEXT = {"nächster", "nächste", "nächstes", "skip", "überspring", "überspringe", "überspringen", "next"}
PREV = {"vorheriger", "vorherige", "vorheriges", "zurück", "previous", "letzter", "letzte", "letztes"}
PHONE_OPEN_BLOCK = {"musik", "die", "das", "den", "licht", "lampe", "taschenlampe", "ordner", "datei", "fenster", "programm"}


def _words(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w\säöüß%]", " ", text.lower())
    return [w for w in cleaned.split() if w not in POLITE]


def detect(text: str, phone_turn: bool, phone_connected: bool, spotify_connected: bool, mail_connected: bool = False, routines_on: bool = False) -> dict | None:
    """-> {'kind','action','params','label'} or None (then the model decides)."""
    raw = (text or "").strip()
    # ---------------------------------------------------------------- "antworte ich komme gleich" (phone): answers the latest chat message
    rm = re.match(r"^(?:antworte|antwort|schreib(?:e)?\s+(?:(?:ihm|ihr|denen)\s+)?zurück|schreib(?:e)?\s+(?:ihm|ihr|denen)|sag(?:e)?\s+(?:ihm|ihr|denen))\s*[:,]?\s+(.{2,300})$", raw.strip(), re.IGNORECASE)
    if rm and phone_turn and phone_connected:
        return {"kind": "phone", "action": "reply_message", "params": {"text": rm.group(1).strip()}, "label": "Antworte auf die Nachricht …"}

    # ---------------------------------------------------------------- weekly review: "Wochenbericht", "wie war meine Woche"
    if re.match(r"^(?:mein(?:en)?\s+|den\s+|der\s+)?(?:wochen\s?(?:bericht|rückblick|rueckblick|übersicht)|rückblick auf die woche|wie war (?:meine|die) woche|was hast du diese woche (?:für mich )?(?:gemacht|getan))$",
                " ".join(re.sub(r"[^\w\säöüß]", " ", raw.lower()).split())):
        return {"kind": "report", "action": "week", "params": {}, "label": "Stelle deinen Wochenrückblick zusammen …"}

    # ---------------------------------------------------------------- shared from the phone ("Share -> Yume"): the phone announces it with a fixed sentence
    im = re.match(r"^ich habe dir gerade (?:eine?|einen) (sprachnachricht|bild|dokument|text|datei) geteilt\b", raw.strip().lower())
    if im and phone_connected:
        return {"kind": "inbox", "action": "read", "params": {"what": im.group(1), "question": raw.strip()}, "label": "Sehe mir das Geteilte an …"}

    # ---------------------------------------------------------------- journal: "schreib ins Tagebuch: ..." / "Tagebuch: ..."
    jm = re.match(r"^(?:schreib(?:e)?|trag(?:e)?|notier(?:e)?|füg(?:e)?|speicher(?:e)?)\s+(?:bitte\s+|mir\s+)*(?:ins|in\s+mein|in\s+das)\s+tagebuch\s*(?:ein|hinzu)?\s*[:,\-]?\s*(.{4,500})$|^tagebuch\s*[:\-]\s*(.{4,500})$", raw.strip(), re.IGNORECASE)
    if jm:
        return {"kind": "journal", "action": "add", "params": {"text": (jm.group(1) or jm.group(2)).strip()}, "label": "Schreibe ins Tagebuch …"}

    if not raw or len(raw) > 70 or "\n" in raw:
        return None
    words = _words(raw)
    if not words or len(words) > 7:
        return None
    ws = set(words)
    if ws & PC_WORDS:
        return None                                              # "... auf dem PC": the model picks the PC tool
    music = bool(ws & MUSIC)
    digits = re.findall(r"\d+", raw)

    # ---------------------------------------------------------------- undo: "mach das rückgängig"
    if re.match(r"^(?:mach\s+(?:das\s+)?|nimm\s+(?:das\s+)?)?(?:rückgängig|zurück)$|^(?:mach|nimm)\s+das\s+(?:wieder\s+)?(?:rückgängig|zurück)$|^das\s+(?:war\s+)?(?:falsch|nicht\s+gewollt)$|^(?:lösch|vergiss)\s+das\s+wieder$", " ".join(re.sub(r"[^\w\säöüß]", " ", raw.lower()).split())):
        return {"kind": "undo", "action": "undo", "params": {}, "label": "Mache es rückgängig …"}

    # ---------------------------------------------------------------- photo questions (phone camera / screen): "was ist das?", "lies das vor"
    if phone_turn and phone_connected:
        low_c = " ".join(re.sub(r"[^\w\säöüß]", " ", raw.lower()).split())
        if re.match(r"^(?:was\s+steht\s+(?:da|hier|dort|darauf)|lies\s+(?:mir\s+)?(?:das|den\s+text)(?:\s+(?:mal\s+)?vor)?|kannst\s+du\s+das\s+lesen)$", low_c):
            return {"kind": "camera", "action": "camera_look", "params": {"prompt": "Read ALL text that is visible in this picture, exactly as written, in the order it appears. If there is none, say so.", "question": raw}, "label": "Lese den Text mit der Kamera …"}
        if re.match(r"^(?:was\s+(?:ist|sind)\s+(?:das|dies|die\s+da|hier)(?:\s+für\s+(?:ein|eine|einen)\s+[\w äöüß]{3,22})?|was\s+siehst\s+du(?:\s+(?:hier|da|gerade))?|(?:schau|sieh|guck)\s+(?:dir\s+)?(?:das\s+)?(?:mal\s+)?an|(?:schau|sieh|guck)\s+mal)\??$", low_c) \
                and "bildschirm" not in low_c:
            return {"kind": "camera", "action": "camera_look", "params": {"prompt": "Describe what the camera sees in 2-3 sentences. If it is a plant, animal, product, dish or object, say what it most likely is.", "question": raw}, "label": "Schaue durch die Kamera …"}
        if re.match(r"^(?:was\s+(?:siehst\s+du|ist\s+(?:gerade\s+)?(?:zu\s+sehen|los)).{0,12}bildschirm|was\s+steht\s+auf\s+(?:meinem\s+)?bildschirm|lies\s+(?:mir\s+)?(?:den\s+)?bildschirm\s+vor)\w*$", low_c) or low_c in ("was ist auf dem bildschirm", "was siehst du auf meinem bildschirm"):
            return {"kind": "camera", "action": "screen_look", "params": {"prompt": "Describe what the phone screen shows and read the important texts.", "question": raw}, "label": "Schaue auf den Handy-Bildschirm …"}

    # ---------------------------------------------------------------- lists: "setz Milch auf die Einkaufsliste", "was steht auf der Einkaufsliste"
    low_sentence = " ".join(re.sub(r"[^\w\säöüß,-]", " ", raw.lower()).split())
    m = re.match(r"^(?:setz|setze|schreib|schreibe|pack|packe|tu|tue|füg|füge|trag|trage|schreib)\s+(.+?)\s+(?:auf|in|zu|zur|zum)\s+(?:die\s+|der\s+|meine\s+|meiner\s+|meinen\s+|meinem\s+)?([\w\säöüß-]{2,30}?)(?:\s+(?:drauf|hinzu|dazu))?$", low_sentence)
    if m and re.search(r"liste|einkauf|todo|to-do|aufgaben", m.group(2)):
        return {"kind": "lists", "action": "add", "params": {"list": m.group(2).strip(), "item": m.group(1).strip()}, "label": "Setze es auf die Liste …"}
    m = re.match(r"^(?:was\s+(?:steht|ist|haben\s+wir)\s+(?:so\s+)?(?:auf|in)\s+(?:der\s+|meiner\s+|meinen\s+)?([\w\säöüß-]{2,30})|zeig\s+(?:mir\s+)?(?:die\s+|meine\s+)?([\w\säöüß-]{2,30}))$", low_sentence)
    if m:
        name = (m.group(1) or m.group(2) or "").strip()
        if re.search(r"liste|einkauf|todo|to-do|aufgaben", name):
            return {"kind": "lists", "action": "show", "params": {"list": name}, "label": "Lese die Liste …"}
    if re.match(r"^(?:was\s+muss\s+ich\s+(?:noch\s+)?(?:kaufen|einkaufen|besorgen)|was\s+brauchen\s+wir\s+noch)$", low_sentence):
        return {"kind": "lists", "action": "show", "params": {"list": "Einkaufsliste"}, "label": "Lese die Einkaufsliste …"}

    # ---------------------------------------------------------------- routines: "Guten Morgen" -> briefing, "Gute Nacht" -> good-night routine
    if routines_on:
        low = " ".join(words)
        if (ws & {"morgen", "moin"} and ws <= {"guten", "morgen", "moin", "hallo", "hi", "na", "zusammen", "wach", "bin", "wieder", "aufgestanden", "aufgewacht", "ich"} and "morgen" in ws
                and "guten" in ws or low in ("moin", "morgen")) or re.search(r"\b(?:briefing|tagesübersicht|tagesueberblick)\b", low) \
                or re.search(r"^(?:was\s+)?(?:steht|liegt|ist)\s+heute\s+(?:so\s+)?(?:an|los)$|^was\s+habe\s+ich\s+heute\s+(?:so\s+)?vor$|^wie\s+sieht\s+mein\s+tag\s+aus$", low):
            return {"kind": "routine", "action": "morning", "params": {}, "label": "Stelle dein Morgen-Briefing zusammen …"}
        if "gute nacht" in low or re.search(r"\bich\s+(?:gehe|geh)\s+(?:jetzt\s+|mal\s+)?(?:schlafen|ins\s+bett)\b", low) or low in ("ab ins bett", "gn8"):
            return {"kind": "routine", "action": "night", "params": {}, "label": "Gute-Nacht-Routine …"}

    # ---------------------------------------------------------------- Spotify (works for the PC and for the phone)
    if spotify_connected:
        if re.search(r"was\s+(?:läuft|spielt)|welch\w+\s+(?:song|lied|titel)\s+(?:läuft|ist das)", raw.lower()):
            return {"kind": "spotify", "action": "now", "params": {}, "label": "Prüfe, was gerade läuft …"}
        if (music or len(words) == 1) and ws & NEXT and not ws & PAUSE:
            return {"kind": "spotify", "action": "next", "params": {}, "label": "Nächster Titel …"}
        if ws & PREV and (music or ws & {"vorheriger", "vorherige", "vorheriges"}) and len(words) <= 4:
            return {"kind": "spotify", "action": "previous", "params": {}, "label": "Voriger Titel …"}
        if music and ws & {"leiser", "lauter"} or ws <= {"leiser", "lauter"} and ws:
            return {"kind": "spotify", "action": "volume_rel", "params": {"delta": -15 if "leiser" in ws else 15},
                    "label": "Mache die Musik leiser …" if "leiser" in ws else "Mache die Musik lauter …"}
        if music and digits and ws & {"lautstärke", "volume", "laut", "leise"}:
            return {"kind": "spotify", "action": "volume", "params": {"level": max(0, min(100, int(digits[0])))},
                    "label": f"Stelle die Musik auf {int(digits[0])} % …"}
        if (music or ws == {"pause"}) and ws & PAUSE and not ws & {"weiter", "wieder", "an", "starte", "spiele", "spiel"} and not digits:
            return {"kind": "spotify", "action": "pause", "params": {}, "label": "Pausiere die Musik …"}
        if ((music and ws & RESUME) or ws & {"weiterspielen", "fortsetzen"} or ws == {"weiter"} or ws == {"spiel", "weiter"} or ws == {"spiele", "weiter"}) \
                and not ws & PAUSE:
            return {"kind": "spotify", "action": "resume", "params": {}, "label": "Setze die Musik fort …"}

    # ---------------------------------------------------------------- mail: "habe ich neue mails?", "fass meine ungelesenen mails zusammen"
    if mail_connected and ws & {"mail", "mails", "email", "emails", "e-mail", "e-mails", "post", "posteingang"} and \
            (ws & {"neue", "neuen", "ungelesene", "ungelesenen", "zusammen", "zusammenfassen", "zusammenfassung", "fass", "fasse", "posteingang", "wichtige", "wichtigen"}
             or raw.lower().startswith(("habe ich", "hab ich", "sind neue", "gibt es"))):
        return {"kind": "mail", "action": "summary", "params": {}, "label": "Lese deine neuen Mails …"}

    # ---------------------------------------------------------------- phone (only when the user talks through the phone)
    if phone_turn and phone_connected:
        if "taschenlampe" in ws:
            on = not (ws & {"aus", "ausmachen", "ausschalten", "off"})
            return {"kind": "phone", "action": "flashlight", "params": {"on": on}, "label": "Schalte die Taschenlampe …"}
        sentence = " ".join(re.sub(r"[^\w\säöüß]", " ", raw.lower()).split())
        sentence = " ".join(w for w in sentence.split() if w not in POLITE)                 # "kannst du mir bitte spotify öffnen" -> "spotify öffnen"
        tail = r"(?:\s+(?:auf|am)\s+(?:dem\s+|meinem\s+)?(?:handy|smartphone))?"
        m = re.match(r"^(?:öffne|öffnen|starte|starten|open)\s+(?:die\s+|den\s+|das\s+)?(?:app\s+)?(.+?)" + tail + "$", sentence) \
            or re.match(r"^(?:die\s+|den\s+|das\s+)?(?:app\s+)?(.+?)\s+(?:öffnen|starten)" + tail + "$", sentence)
        if m:
            name = m.group(1).strip()
            if name and len(name.split()) <= 3 and not set(name.split()) & PHONE_OPEN_BLOCK and not any(ch.isdigit() for ch in name):
                return {"kind": "phone", "action": "open_app", "params": {"app": name}, "label": f"Öffne {name} …"}
    return None


async def execute(cmd: dict, bridge) -> tuple[bool, str]:
    """Runs a detected command. Returns (success, short result text)."""
    kind, action, params = cmd["kind"], cmd["action"], cmd.get("params", {})
    if kind == "spotify":
        from app.utils import spotify_pc

        def run():
            if action == "now":
                n = spotify_pc.now_playing(0)
                if n.get("title"):
                    return True, f"{'Es läuft' if n.get('playing') else 'Pausiert'}: {n['title']} von {n.get('artist', '')}"
                return True, n.get("error") or "Gerade läuft nichts."
            if action == "volume_rel":
                n = spotify_pc.now_playing(0)
                level = int(n.get("volume") if n.get("volume") is not None else 50) + int(params.get("delta", 0))
                ok, text = spotify_pc.control("volume", max(0, min(100, level)))
                return ok, (f"Lautstärke jetzt {max(0, min(100, level))} %." if ok else text)
            ok, text = spotify_pc.control(action, params.get("level"))
            if ok and action in ("pause", "resume"):
                cmd["undo"] = {"kind": "spotify", "action": "resume" if action == "pause" else "pause"}
            return ok, ({"pause": "Musik pausiert.", "resume": "Musik läuft weiter.", "next": "Nächster Titel.", "previous": "Voriger Titel.",
                         "volume": f"Lautstärke auf {params.get('level')} %."}.get(action, "ok") if ok else text)
        return await asyncio.to_thread(run)
    if kind == "journal":
        from app.utils import journal

        def write_entry():
            item = journal.add(params["text"])
            if item:
                cmd["undo"] = {"kind": "journal_add", "id": item["id"]}
                return True, "Ins Tagebuch geschrieben."
            return False, "Der Eintrag ist zu kurz."
        return await asyncio.to_thread(write_entry)
    if kind == "camera":
        from app.utils.ai_clients.tools import PhoneControlTool
        res = await PhoneControlTool().execute({"action": action, "prompt": params.get("prompt", ""), "facing": "back"}, {})
        return bool(res.get("success")), str(res.get("result", ""))
    if kind == "scene":
        from app.utils import ha_scenes
        return await ha_scenes.activate(params["entity"])
    if kind == "undo":
        from app.utils import tool_log
        return await asyncio.to_thread(tool_log.undo, "")
    if kind == "lists":
        from app.utils import lists_store as ls

        def run_lists():
            if action == "add":
                key, added = ls.add(params["list"], params["item"])
                if added:
                    cmd["undo"] = {"kind": "list_add", "list": key, "ids": [i["id"] for i in added]}
                return True, ("Auf die " + key + " gesetzt: " + ", ".join(i["text"] for i in added)) if added else f"Stand schon auf der {key}."
            return True, ls.format_text(ls.show(params.get("list", "")))
        return await asyncio.to_thread(run_lists)
    if kind == "mail":
        from app.utils import organizer

        def mails():
            try:
                items = organizer.mail_list(8, True, "")
            except Exception as exc:
                return False, f"Mail-Fehler: {str(exc)[:120]}"
            if not items:
                return True, "Keine ungelesenen Mails."
            return True, "\n".join(f"- {m['date']} | {m['from']} | {m['subject']} | {m['snippet'][:160]}" for m in items)
        return await asyncio.to_thread(mails)
    if kind == "phone":
        if bridge is None or not bridge.has_phone():
            return False, "Es ist kein Handy verbunden."
        reply = await bridge.phone_command(action, params, timeout=20.0)
        if not reply.get("ok"):
            return False, f"Handy: {reply.get('error') or reply.get('message') or 'fehlgeschlagen'}"
        data = reply.get("data")
        return True, data if isinstance(data, str) and data else ("Taschenlampe an." if action == "flashlight" and params.get("on") else "Erledigt.")
    return False, "unbekannt"
