import re
import torch
import numpy as np
import json
import logging
import datetime
import asyncio
import shutil
import hashlib
import threading
from pathlib import Path
from typing import Callable, Awaitable, Optional
from app.configuration import configuration
from app.utils.embedding_provider import get_embedder as _get_embedder

logger = logging.getLogger("SoulMemory")

STATE_SCHEMA_VERSION = 2
HEALING_LOG_CAP     = 15
CORE_IDENTITY_CAP   = 12
USER_LIST_CAP       = 25

_TRUST_LEVELS = frozenset({
    "Distrustful", "Wary", "Neutral", "Developing Trust", "Deeply Bound", "Unstable",
})

_FACT_DATE_SUFFIX_RE = re.compile(r"\s*\(since\s+(\d{4}-\d{2}-\d{2})\)\s*$", re.IGNORECASE)


def _today() -> str:
    return datetime.date.today().isoformat()


def _normalize_fact(text) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    return s.strip("\"'`“”‘’«»!.…?;:,")


def _strip_date_suffix(text: str) -> str:
    return _FACT_DATE_SUFFIX_RE.sub("", str(text or "")).strip()


def _extract_fact_date(text: str) -> str:
    m = _FACT_DATE_SUFFIX_RE.search(str(text or ""))
    return m.group(1) if m else ""


def _fact_as_dict(f) -> dict:
    if isinstance(f, dict):
        return {"text": str(f.get("text", "")).strip(), "date": str(f.get("date", "") or "")}
    return {"text": _strip_date_suffix(str(f)), "date": _extract_fact_date(str(f))}


def _default_char_state(character_name: str) -> dict:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "character": character_name,
        "core_identity": [],
        "internal_state": {
            "primary_emotion": "Calm",
            "intensity": 3,
            "psychological_tension": "None.",
            "emotional_decay_counter": 0,
        },
        "cognitive_drive": {
            "active_agenda": "Observing and responding.",
            "immediate_focus": "The current conversation.",
        },
        "cognitive_dissonance": "None.",
        "healing_log": [],
    }


def _default_user_state(user_name: str) -> dict:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "user": user_name,
        "role_in_story": "User",
        "known_attributes": "None.",
        "trust_level": "Neutral",
        "dynamic_description": "No dynamic registered.",
        "unspoken_tension": "None.",
        "preferences_habits": [],
        "shared_milestones_promises": [],
    }


def _fill_defaults(state: dict, defaults: dict):
    """Recursively add missing default keys."""
    for k, v in defaults.items():
        if k not in state:
            state[k] = json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v
        elif isinstance(v, dict) and isinstance(state[k], dict):
            _fill_defaults(state[k], v)
    return state


def _load_json_state(json_path: Path, defaults: dict) -> Optional[dict]:
    if not json_path.exists():
        return None
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return _fill_defaults(data, defaults)
    except Exception as e:
        logger.warning(f"[Soul Memory] Failed to load state {json_path.name}: {e}")
        return None


def _save_json_state(json_path: Path, state: dict) -> bool:
    tmp = json_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(json_path)
        return True
    except Exception as e:
        logger.error(f"[Soul Memory] State write error for {json_path.name}: {e}")
        tmp.unlink(missing_ok=True)
        return False

_DE_LABELS = [
    ("# USER PROFILE & RELATIONSHIP MEMORY:", "# BENUTZERPROFIL & BEZIEHUNGSGEDÄCHTNIS:"),
    ("## USER IDENTITY & STATUS", "## IDENTITÄT & STATUS DES BENUTZERS"),
    ("## RELATIONSHIP METADATA", "## BEZIEHUNGSDATEN"),
    ("## PREFERENCES & HABITS", "## VORLIEBEN & GEWOHNHEITEN"),
    ("## SHARED MILESTONES & PROMISES", "## GEMEINSAME MEILENSTEINE & VERSPRECHEN"),
    ("**Role in Story**", "**Rolle in der Geschichte**"), ("**Known Attributes**", "**Bekannte Eigenschaften**"),
    ("**Trust Level**", "**Vertrauensstufe**"), ("**Current Dynamic**", "**Aktuelle Dynamik**"), ("**Unspoken Tension**", "**Unausgesprochene Spannung**"),
    ("# SOUL CACHE:", "# SEELEN-SPEICHER:"),
    ("## CORE IDENTITY & UNBREAKABLE BELIEFS", "## KERNIDENTITÄT & UNERSCHÜTTERLICHE ÜBERZEUGUNGEN"),
    ("## INTERNAL STATE & PSYCHOLOGICAL MOMENTUM", "## INNERER ZUSTAND & PSYCHISCHE DYNAMIK"),
    ("**Primary Emotion**", "**Hauptgefühl**"), ("(Intensity:", "(Intensität:"), ("**Psychological Tension**", "**Psychische Spannung**"),
    ("**Emotional Decay Counter**", "**Zähler für abklingende Gefühle**"),
    ("## COGNITIVE DRIVE & ACTIVE AGENDA", "## ANTRIEB & AKTUELLE AGENDA"), ("**Active Agenda**", "**Aktuelle Agenda**"), ("**Immediate Focus**", "**Unmittelbarer Fokus**"),
    ("## UNRESOLVED COGNITIVE DISSONANCE", "## UNGELÖSTE KOGNITIVE DISSONANZ"),
    ("## RESOLVED CONTRADICTIONS (HEALING LOG)", "## GELÖSTE WIDERSPRÜCHE (HEILUNGSPROTOKOLL)"),
    (" (since ", " (seit "),
]


def localize_markdown(text: str) -> str:
    """Display only: translates the fixed headings / labels of the memory files when the program language is German (the files on disk stay as they are)."""
    try:
        german = int(configuration.ConfigurationSettings().get_main_setting("program_language") or 0) == 2
    except Exception:
        return text
    if not german:
        return text
    for a, b in _DE_LABELS:
        text = text.replace(a, b)
    return text


def render_char_markdown(state: dict, character_name: str) -> str:
    ist   = state.get("internal_state", {}) or {}
    drive = state.get("cognitive_drive", {}) or {}

    try:
        intensity = max(1, min(5, int(ist.get("intensity", 3))))
    except (TypeError, ValueError):
        intensity = 3
    try:
        decay = max(0, int(ist.get("emotional_decay_counter", 0) or 0))
    except (TypeError, ValueError):
        decay = 0

    lines = [
        f"# SOUL CACHE: {str(character_name).upper()}",
        "",
        "## CORE IDENTITY & UNBREAKABLE BELIEFS",
    ]
    for f in state.get("core_identity", []) or []:
        fd = _fact_as_dict(f)
        if not fd["text"]:
            continue
        suffix = f" (since {fd['date']})" if fd["date"] else ""
        lines.append(f"- {fd['text']}{suffix}")

    lines += [
        "",
        "## INTERNAL STATE & PSYCHOLOGICAL MOMENTUM",
        f"- **Primary Emotion**: {ist.get('primary_emotion', 'Calm')} (Intensity: {intensity}/5)",
        f"- **Psychological Tension**: {ist.get('psychological_tension', 'None.')}",
        f"- **Emotional Decay Counter**: {decay}/3",
        "",
        "## COGNITIVE DRIVE & ACTIVE AGENDA",
        f"- **Active Agenda**: {drive.get('active_agenda', 'Observing and responding.')}",
        f"- **Immediate Focus**: {drive.get('immediate_focus', 'The current conversation.')}",
        "",
        "## UNRESOLVED COGNITIVE DISSONANCE",
        str(state.get("cognitive_dissonance", "None.") or "None."),
    ]

    healing = state.get("healing_log", []) or []
    if healing:
        lines += ["", "## RESOLVED CONTRADICTIONS (HEALING LOG)"]
        for entry in healing[-HEALING_LOG_CAP:]:
            ed = _fact_as_dict(entry) if not isinstance(entry, dict) else entry
            date = str(ed.get("date", "") or "")
            text = str(ed.get("text", ed.get("entry", "")) or "").strip()
            if text:
                lines.append(f"- [{date}] {text}" if date else f"- {text}")

    return "\n".join(lines)


def render_user_markdown(state: dict, user_name: str) -> str:
    lines = [
        f"# USER PROFILE & RELATIONSHIP MEMORY: {str(user_name).upper()}",
        "",
        "## USER IDENTITY & STATUS",
        f"- **Role in Story**: {state.get('role_in_story', 'User')}",
        f"- **Known Attributes**: {state.get('known_attributes', 'None.')}",
        "",
        "## RELATIONSHIP METADATA",
        f"- **Trust Level**: {state.get('trust_level', 'Neutral')}",
        f"- **Current Dynamic**: {state.get('dynamic_description', 'No dynamic registered.')}",
        f"- **Unspoken Tension**: {state.get('unspoken_tension', 'None.')}",
        "",
        "## PREFERENCES & HABITS",
    ]
    for f in state.get("preferences_habits", []) or []:
        fd = _fact_as_dict(f)
        if fd["text"]:
            lines.append(_fmt_fact_line(fd))
    lines += ["", "## SHARED MILESTONES & PROMISES"]
    for f in state.get("shared_milestones_promises", []) or []:
        fd = _fact_as_dict(f)
        if fd["text"]:
            lines.append(_fmt_fact_line(fd))
    return "\n".join(lines)


def _fmt_fact_line(fd: dict) -> str:
    suffix = f" (since {fd['date']})" if fd.get("date") else ""
    return f"- {fd['text']}{suffix}"


_SECTION_RE = re.compile(r"^#{1,2}\s+(.+?)\s*$")


def parse_char_markdown(md: str, character_name: str) -> dict:
    state = _default_char_state(character_name)
    section = None
    for raw in str(md or "").splitlines():
        line = raw.rstrip()
        header = _SECTION_RE.match(line)
        if header:
            title = header.group(1).upper()
            if title.startswith("CORE IDENTITY"):
                section = "identity"
            elif title.startswith("INTERNAL STATE"):
                section = "state"
            elif title.startswith("COGNITIVE DRIVE"):
                section = "drive"
            elif title.startswith("UNRESOLVED COGNITIVE"):
                section = "dissonance"
            elif title.startswith("RESOLVED CONTRADICTIONS"):
                section = "healing"
            else:
                section = None
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("# "):
            continue

        if section == "identity":
            text = stripped.lstrip("-* ").strip()
            if text:
                state["core_identity"].append(
                    {"text": _strip_date_suffix(text), "date": _extract_fact_date(text)}
                )
        elif section == "state":
            em = re.match(r"-\s*\*\*Primary Emotion\*\*:\s*(.*?)(?:\s*\(Intensity:\s*(\d)(?:\s*/\s*5)?\))?\s*$", stripped, re.IGNORECASE)
            if em:
                if em.group(1).strip():
                    state["internal_state"]["primary_emotion"] = em.group(1).strip()
                if em.group(2):
                    state["internal_state"]["intensity"] = max(1, min(5, int(em.group(2))))
                continue
            tm = re.match(r"-\s*\*\*Psychological Tension\*\*:\s*(.*)$", stripped, re.IGNORECASE)
            if tm:
                state["internal_state"]["psychological_tension"] = tm.group(1).strip() or "None."
                continue
            cm = re.match(r"-\s*\*\*Emotional Decay Counter\*\*:\s*(\d+)", stripped, re.IGNORECASE)
            if cm:
                state["internal_state"]["emotional_decay_counter"] = int(cm.group(1))
        elif section == "drive":
            am = re.match(r"-\s*\*\*Active Agenda\*\*:\s*(.*)$", stripped, re.IGNORECASE)
            if am:
                state["cognitive_drive"]["active_agenda"] = am.group(1).strip() or "Observing and responding."
                continue
            fm = re.match(r"-\s*\*\*Immediate Focus\*\*:\s*(.*)$", stripped, re.IGNORECASE)
            if fm:
                state["cognitive_drive"]["immediate_focus"] = fm.group(1).strip() or "The current conversation."
        elif section == "dissonance":
            current = str(state.get("cognitive_dissonance", "None."))
            chunk = stripped.lstrip("-* ").strip()
            if chunk:
                state["cognitive_dissonance"] = chunk if current in ("None.", "") else f"{current}\n{chunk}"
        elif section == "healing":
            hm = re.match(r"-\s*\[(\d{4}-\d{2}-\d{2})[^\]]*\]\s*(.*)$", stripped)
            if hm:
                state["healing_log"].append({"date": hm.group(1), "text": hm.group(2).strip()})
            else:
                text = stripped.lstrip("-* ").strip()
                if text:
                    state["healing_log"].append({"date": "", "text": text})
    return state


def parse_user_markdown(md: str, user_name: str) -> dict:
    state = _default_user_state(user_name)
    section = None
    for raw in str(md or "").splitlines():
        line = raw.rstrip()
        header = _SECTION_RE.match(line)
        if header:
            title = header.group(1).upper()
            if title.startswith("USER IDENTITY"):
                section = "identity"
            elif title.startswith("RELATIONSHIP METADATA"):
                section = "meta"
            elif title.startswith("PREFERENCES"):
                section = "prefs"
            elif title.startswith("SHARED MILESTONES"):
                section = "milestones"
            else:
                section = None
            continue

        stripped = line.strip()
        if not stripped or stripped.startswith("# "):
            continue

        if section == "identity":
            rm = re.match(r"-\s*\*\*Role in Story\*\*:\s*(.*)$", stripped, re.IGNORECASE)
            if rm:
                state["role_in_story"] = rm.group(1).strip() or "User"
                continue
            km = re.match(r"-\s*\*\*Known Attributes\*\*:\s*(.*)$", stripped, re.IGNORECASE)
            if km:
                state["known_attributes"] = km.group(1).strip() or "None."
        elif section == "meta":
            tm = re.match(r"-\s*\*\*Trust Level\*\*:\s*(.*)$", stripped, re.IGNORECASE)
            if tm:
                state["trust_level"] = tm.group(1).strip() or "Neutral"
                continue
            dm = re.match(r"-\s*\*\*Current Dynamic\*\*:\s*(.*)$", stripped, re.IGNORECASE)
            if dm:
                state["dynamic_description"] = dm.group(1).strip() or "No dynamic registered."
                continue
            um = re.match(r"-\s*\*\*Unspoken Tension\*\*:\s*(.*)$", stripped, re.IGNORECASE)
            if um:
                state["unspoken_tension"] = um.group(1).strip() or "None."
        elif section in ("prefs", "milestones"):
            text = stripped.lstrip("-* ").strip()
            if text:
                fact = {"text": _strip_date_suffix(text), "date": _extract_fact_date(text)}
                key = "preferences_habits" if section == "prefs" else "shared_milestones_promises"
                state[key].append(fact)
    return state


def _add_facts(lst: list, items, provenance_date: str, cap: int) -> int:
    existing = {_normalize_fact(_fact_as_dict(f)["text"]) for f in lst}
    added = 0
    for item in items or []:
        text = str(item or "").strip()
        if not text:
            continue
        key = _normalize_fact(text)
        if not key or key in existing:
            continue
        lst.append({"text": text, "date": provenance_date})
        existing.add(key)
        added += 1
    if len(lst) > cap:
        del lst[: len(lst) - cap]
    return added


def _remove_facts(lst: list, patterns) -> tuple[list, list]:
    pat_norms = [_normalize_fact(p) for p in (patterns or []) if str(p or "").strip()]
    if not pat_norms:
        return lst, []
    kept, removed = [], []
    for f in lst:
        text = _fact_as_dict(f)["text"]
        norm = _normalize_fact(text)
        if any(p == norm or (p in norm and len(p) >= 8) for p in pat_norms):
            removed.append(text)
        else:
            kept.append(f)
    return kept, removed


def _advance_emotional_decay(state: dict, emotion_active: Optional[bool]) -> bool:
    ist = state.setdefault("internal_state", {})
    if emotion_active is None:
        return False
    if emotion_active is True:
        ist["emotional_decay_counter"] = 0
        return False

    try:
        counter = int(ist.get("emotional_decay_counter", 0) or 0)
    except (TypeError, ValueError):
        counter = 0
    counter += 1

    if counter >= 3:
        try:
            intensity = int(ist.get("intensity", 3))
        except (TypeError, ValueError):
            intensity = 3
        ist["intensity"] = max(1, min(5, intensity - 1))
        ist["emotional_decay_counter"] = 0
        logger.info("[Soul Memory] Emotional decay triggered: intensity softened.")
        return True

    ist["emotional_decay_counter"] = counter
    return False


def apply_character_patch(state: dict, patch: dict, provenance_date: str) -> list:
    changes = []
    if not isinstance(patch, dict):
        return changes

    identity = state.setdefault("core_identity", [])
    removed_n = 0
    if patch.get("core_identity_remove"):
        identity, removed = _remove_facts(identity, patch.get("core_identity_remove"))
        removed_n = len(removed)
        state["core_identity"] = identity
    added_n = _add_facts(identity, patch.get("core_identity_add"), provenance_date, CORE_IDENTITY_CAP)
    if removed_n:
        changes.append(f"core_identity: -{removed_n}")
    if added_n:
        changes.append(f"core_identity: +{added_n}")

    emotion_active = None
    ist_patch = patch.get("internal_state")
    if isinstance(ist_patch, dict):
        if isinstance(ist_patch.get("emotion_active"), bool):
            emotion_active = ist_patch["emotion_active"]
        ist = state.setdefault("internal_state", {})
        pe = ist_patch.get("primary_emotion")
        if isinstance(pe, str) and pe.strip():
            ist["primary_emotion"] = pe.strip()
        inten = ist_patch.get("intensity")
        if isinstance(inten, (int, float)) and not isinstance(inten, bool):
            ist["intensity"] = max(1, min(5, int(round(inten))))
        pt = ist_patch.get("psychological_tension")
        if isinstance(pt, str) and pt.strip():
            ist["psychological_tension"] = pt.strip()

    if _advance_emotional_decay(state, emotion_active):
        changes.append("emotion decayed")

    drive_patch = patch.get("cognitive_drive")
    if isinstance(drive_patch, dict):
        drive = state.setdefault("cognitive_drive", {})
        aa = drive_patch.get("active_agenda")
        if isinstance(aa, str) and aa.strip():
            drive["active_agenda"] = aa.strip()
        focus = drive_patch.get("immediate_focus")
        if isinstance(focus, str) and focus.strip():
            drive["immediate_focus"] = focus.strip()

    dissonance = patch.get("cognitive_dissonance")
    if isinstance(dissonance, str) and dissonance.strip():
        state["cognitive_dissonance"] = dissonance.strip()

    return changes


def apply_user_patch(state: dict, patch: dict, provenance_date: str) -> list:
    changes = []
    if not isinstance(patch, dict):
        return changes

    identity = patch.get("user_identity_status")
    if isinstance(identity, dict):
        role = identity.get("role_in_story")
        if isinstance(role, str) and role.strip():
            state["role_in_story"] = role.strip()
        attrs = identity.get("known_attributes")
        if isinstance(attrs, str) and attrs.strip():
            state["known_attributes"] = attrs.strip()

    rel = patch.get("relationship_metadata")
    if isinstance(rel, dict):
        trust = rel.get("trust_level")
        if isinstance(trust, str) and trust.strip():
            trust_s = trust.strip()
            state["trust_level"] = trust_s if trust_s in _TRUST_LEVELS else trust_s
            if trust_s not in _TRUST_LEVELS:
                logger.debug(f"[Soul Memory] Non-standard trust level stored: '{trust_s}'")
        dynamic = rel.get("dynamic_description")
        if isinstance(dynamic, str) and dynamic.strip():
            state["dynamic_description"] = dynamic.strip()
        tension = rel.get("unspoken_tension")
        if isinstance(tension, str) and tension.strip():
            state["unspoken_tension"] = tension.strip()

    for list_key, cap in (
        ("preferences_habits", USER_LIST_CAP),
        ("shared_milestones_promises", USER_LIST_CAP),
    ):
        lst = state.setdefault(list_key, [])
        if patch.get(f"{list_key}_remove"):
            lst, removed = _remove_facts(lst, patch.get(f"{list_key}_remove"))
            if removed:
                changes.append(f"{list_key}: -{len(removed)}")
            state[list_key] = lst
        added = _add_facts(lst, patch.get(f"{list_key}_add"), provenance_date, cap)
        if added:
            changes.append(f"{list_key}: +{added}")

    return changes


def append_healing_entries(state: dict, entries, provenance_date: str) -> int:
    hl = state.setdefault("healing_log", [])
    added = 0
    for entry in entries or []:
        text = str(entry or "").strip()
        if not text or text.lower().startswith(("no conflict", "no contradictions")):
            continue
        hl.append({"date": provenance_date, "text": text})
        added += 1
    if len(hl) > HEALING_LOG_CAP:
        del hl[: len(hl) - HEALING_LOG_CAP]
    return added

_PROMPT_VEC_CACHE: dict = {}
_PROMPT_VEC_LOCK = threading.Lock()

_STOPWORDS = set("""aber alle also auch dann dass dein deine dich dir doch dort eine einen einem einer eines euch habe haben hast hatte
hier ihre immer jetzt kann kein keine mach machen mehr mein meine mich mir nach nein nicht noch nur oder sehr sein sind soll sonst und uns
unter viel vom von war waren was weil wenn wer wie wieder will wir wird wirst wo wollen zum zur ueber über
about after again also because been before being could does doing from have here into just like more most much only other over said same
should some such than that their them then there these they this those through very want were what when where which while will with would your""".split())


def _tokens(text: str) -> set:
    """Content words as 6-letter stems ('Geburtstagsessen' and 'Geburtstag' meet at 'geburt')."""
    return {w[:6] for w in re.findall(r"[a-zA-ZäöüÄÖÜß0-9]{4,}", str(text).lower()) if w not in _STOPWORDS}


def compact_markdown(text: str, limit: int) -> str:
    """Shortens a memory markdown to `limit` characters WITHOUT cutting the later sections off: every `## section` gets its share of
    the budget (whole lines only), so the end of the file (milestones, promises ...) survives as well as the beginning."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    sections, current = [], []
    for line in text.splitlines():
        if line.startswith("#") and current:
            sections.append(current)
            current = []
        current.append(line)
    if current:
        sections.append(current)
    if len(sections) <= 1:
        return text[:limit].rsplit("\n", 1)[0]
    head = sum(len(s[0]) + 1 for s in sections)
    budget = max(80, (limit - head) // len(sections))
    out = []
    for s in sections:
        out.append(s[0])
        used = 0
        for line in s[1:]:
            if used + len(line) + 1 > budget and used > 0:
                out.append("  [...]")
                break
            out.append(line)
            used += len(line) + 1
    return "\n".join(out)[:limit + 200]


def encode_topic_cached(cache_key: str, target_text: str, embedder) -> np.ndarray:
    digest = hashlib.md5(str(target_text).encode("utf-8", "ignore")).hexdigest()
    with _PROMPT_VEC_LOCK:
        hit = _PROMPT_VEC_CACHE.get(cache_key)
        if hit is not None and hit[0] == digest:
            return hit[1]

    vec = embedder.encode([f"passage: {target_text}"], convert_to_numpy=True)[0]
    with _PROMPT_VEC_LOCK:
        _PROMPT_VEC_CACHE[cache_key] = (digest, vec)
    return vec


def invalidate_memory_vectors(character_name: str, chat_id: str = None):
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in character_name).strip()
    marker = f"/.soul/{safe_name}/chats/"
    chat_seg = f"/chats/{''.join(c if c.isalnum() or c in ' _-' else '_' for c in str(chat_id)).strip()}/" if chat_id else None

    with TopicRAG._CACHE_LOCK:
        for key in list(TopicRAG._VECTOR_CACHE.keys()):
            norm = str(key).replace("\\", "/")
            if marker not in norm:
                continue
            if chat_seg and chat_seg not in norm:
                continue
            TopicRAG._VECTOR_CACHE.pop(key, None)

    prefix = f"topic_{character_name}_"
    with _PROMPT_VEC_LOCK:
        for key in list(_PROMPT_VEC_CACHE.keys()):
            if str(key).startswith(prefix):
                _PROMPT_VEC_CACHE.pop(key, None)

    logger.info(f"[Soul Memory] Vector caches invalidated for '{character_name}'"
                + (f" (chat '{chat_id}')" if chat_id else ""))

_ui_notifier: Optional[Callable] = None


def set_soul_memory_notifier(callback: Callable):
    global _ui_notifier
    _ui_notifier = callback


def _notify_ui(title: str, text: str, msg_type: str = "warning"):
    callback = _ui_notifier
    if not callback:
        return
    try:
        callback(title=title, text=text, msg_type=msg_type)
    except TypeError:
        try:
            callback(title, text, msg_type)
        except Exception:
            pass
    except Exception:
        pass


class TopicRAG:
    """
    RAG over per-character topic files with vector caching.
    """
    RAG_THRESHOLD = 4
    EMBED_CHARS   = 600
    PASS_CHARS    = 8000

    USE_E5_PREFIXES   = True
    E5_QUERY_PREFIX   = "query: "
    E5_PASSAGE_PREFIX = "passage: "

    _VECTOR_CACHE: dict[str, dict[str, tuple[str, np.ndarray]]] = {}
    _CACHE_LOCK = threading.Lock()

    def __init__(self, topics_dir: Path):
        self.topics_dir = topics_dir

    def _cache_bucket(self) -> dict:
        key = str(self.topics_dir.resolve())
        with self._CACHE_LOCK:
            return self._VECTOR_CACHE.setdefault(key, {})

    def _encode_topics_cached(self, embedder, names: list[str], snippets: list[str]) -> np.ndarray:
        bucket  = self._cache_bucket()
        hashes  = [hashlib.md5(s.encode("utf-8", "ignore")).hexdigest() for s in snippets]
        vectors: list = [None] * len(names)
        missing_idx = []

        with self._CACHE_LOCK:
            for i, (name, h) in enumerate(zip(names, hashes)):
                cached = bucket.get(name)
                if cached is not None and cached[0] == h:
                    vectors[i] = cached[1]
                else:
                    missing_idx.append(i)

        if missing_idx:
            raw_missing_snippets = [snippets[i] for i in missing_idx]
            prefixed_snippets = [
                f"{self.E5_PASSAGE_PREFIX}{s}" if self.USE_E5_PREFIXES else s
                for s in raw_missing_snippets
            ]
            
            new_vecs = embedder.encode(prefixed_snippets, convert_to_numpy=True)
            with self._CACHE_LOCK:
                for pos, i in enumerate(missing_idx):
                    vec = new_vecs[pos]
                    vectors[i] = vec
                    bucket[names[i]] = (hashes[i], vec)

        with self._CACHE_LOCK:
            stale = set(bucket.keys()) - set(names)
            for s in stale:
                bucket.pop(s, None)

        return np.vstack(vectors)

    def _load_all_topics(self) -> dict[str, str]:
        result = {}
        if not self.topics_dir.exists():
            return result
        
        try:
            paths = sorted(
                self.topics_dir.glob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            paths = list(self.topics_dir.glob("*.md"))
        for p in paths:
            try:
                result[p.name] = p.read_text(encoding="utf-8")
            except Exception:
                pass
        return result

    def get_relevant_topics(self, query_text: str, max_topics: int = 3) -> dict[str, str]:
        all_topics = self._load_all_topics()
        if not all_topics:
            return {}

        if len(all_topics) <= self.RAG_THRESHOLD:
            return {k: v[:self.PASS_CHARS] for k, v in all_topics.items()}

        try:
            ranked = self.search(query_text, max_topics=max_topics)
            selected = {name: text[:self.PASS_CHARS] for name, text, _score in ranked}
            if selected:
                logger.info(f"[Soul Memory] RAG selected {len(selected)}/{len(all_topics)} topics: {list(selected.keys())}")
                return selected
        except Exception as e:
            logger.warning(f"[Soul Memory] RAG ranking error ({e}). Using fallback.")
        items = list(all_topics.items())[:max_topics]
        return {k: v[:self.PASS_CHARS] for k, v in items}

    @staticmethod
    def _recency_bonus(name: str, mtime: float) -> float:
        """Diaries and recently touched topics are a little more likely to be relevant."""
        age_days = max(0.0, (datetime.datetime.now().timestamp() - mtime) / 86400.0)
        if name.lower().startswith("diary_"):
            return 0.06 if age_days <= 2 else 0.03 if age_days <= 7 else 0.0
        return 0.03 if age_days <= 3 else 0.0

    def search(self, query_text: str, max_topics: int = 3, min_score: float = None, min_overlap: int = 2) -> list[tuple]:
        """Ranks all topic files for a query. Score = cosine similarity (embedding model) + 0.30 * word overlap + recency.
        Without the embedding model the ranking falls back to word overlap alone, so memory stays useful instead of vanishing.
        `min_score` (with the model) / `min_overlap` shared words (without) drop irrelevant topics. Returns [(name, text, score)]."""
        if not self.topics_dir.exists():
            return []
        entries = []
        for p in self.topics_dir.glob("*.md"):
            try:
                entries.append((p.name, p.read_text(encoding="utf-8"), p.stat().st_mtime))
            except Exception:
                continue
        if not entries:
            return []

        q_tokens = _tokens(query_text)
        lex = []
        for name, text, _m in entries:
            t_tokens = _tokens(name.replace("_", " ").replace("-", " ").replace(".md", "")) | _tokens(text[:2500])
            lex.append(len(q_tokens & t_tokens))

        cos = None
        embedder = _get_embedder()
        if embedder:
            try:
                snippets = [t[: self.EMBED_CHARS] for _n, t, _m in entries]
                query_vec = embedder.encode(f"{self.E5_QUERY_PREFIX}{str(query_text)[:1000]}" if self.USE_E5_PREFIXES else str(query_text)[:1000],
                                            convert_to_numpy=True)
                topic_vecs = self._encode_topics_cached(embedder, [n for n, _t, _m in entries], snippets)
                q = query_vec / (np.linalg.norm(query_vec) + 1e-9)
                tv = topic_vecs / (np.linalg.norm(topic_vecs, axis=1, keepdims=True) + 1e-9)
                cos = tv @ q
            except Exception as e:
                logger.warning(f"[Soul Memory] RAG embedding error ({e}); using word overlap only.")
                cos = None

        baseline = 0.76                                     # typical score of an unrelated topic (e5 model) when there are too few topics to measure it
        gap = 0.04
        if cos is not None and len(entries) >= 4:
            baseline = float(np.median(cos))           # measured on this memory itself
            gap = 0.07
        ranked = []
        for i, (name, text, mtime) in enumerate(entries):
            overlap = lex[i]
            lex_score = min(1.0, overlap / 5.0)
            if cos is not None:
                score = float(cos[i]) + 0.30 * lex_score + self._recency_bonus(name, mtime)
                if min_score is not None and (score < min_score or (score - baseline < gap and overlap < min_overlap)):
                    continue
            else:
                score = lex_score + self._recency_bonus(name, mtime) * 0.5
                if min_score is not None and overlap < min_overlap:
                    continue
            ranked.append((name, text, score))
        ranked.sort(key=lambda r: r[2], reverse=True)
        return ranked[:max_topics]

    DEDUP_THRESHOLD = 0.82

    def find_similar_topic(self, query_text: str, threshold: float = None) -> Optional[str]:
        threshold = self.DEDUP_THRESHOLD if threshold is None else threshold

        all_topics = self._load_all_topics()
        if not all_topics:
            return None

        embedder = _get_embedder()
        if not embedder:
            return None

        try:
            names    = list(all_topics.keys())
            snippets = [v[:self.EMBED_CHARS] for v in all_topics.values()]

            safe_query_text = str(query_text)[:1000]
            formatted_query = f"{self.E5_QUERY_PREFIX}{safe_query_text}" if self.USE_E5_PREFIXES else safe_query_text
            query_vec  = embedder.encode(formatted_query, convert_to_numpy=True)
            topic_vecs = self._encode_topics_cached(embedder, names, snippets)

            q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)
            t_norm = topic_vecs / (np.linalg.norm(topic_vecs, axis=1, keepdims=True) + 1e-9)
            scores = t_norm @ q_norm

            best_idx = int(np.argmax(scores))
            if scores[best_idx] >= threshold:
                logger.info(
                    f"[Soul Memory] Dedup match: '{names[best_idx]}' "
                    f"(similarity={scores[best_idx]:.3f} >= {threshold})"
                )
                return names[best_idx]

        except Exception as e:
            logger.warning(f"[Soul Memory] Dedup similarity check failed: {e}")

        return None


_ROUTER_SYSTEM = """\
[SOUL MEMORY — ROUTER AGENT]
You manage the deep cognitive, emotional, and relationship INDEX for "{character}".
You operate strictly as an analytical database engine. Your output MUST be a single, well-formatted JSON object and NOTHING else. No conversational filler, no markdown wrapping outside of the JSON block.

You will receive:
  1. CURRENT CHARACTER MEMORY (MEMORY.md) — includes a RESOLVED CONTRADICTIONS log
  2. CURRENT USER PROFILE & RELATIONSHIP STATE (USER.md)
  3. RECENT MESSAGES (the latest dialogue turns). Lines prefixed with "[Overheard]" were spoken by someone else in {character}'s presence — treat them as witnessed second-hand speech, NOT as {character}'s own experience or actions.
  4. TRIGGERED WORLD LORE (if active)
  5. RELEVANT TOPIC FILES (associated episodic memories)

OUTPUT FORMAT — A FIELD PATCH, NOT A FULL REWRITE:
Emit ONLY the fields that actually changed during this batch. Omit every unchanged field entirely — never re-list old facts.

{
  "no_significant_change": false,
  "character_memory_patch": {
    "core_identity_add": ["NEW unbreakable beliefs, foundational self-conceptions, or fatal flaws of {character} revealed in this batch"],
    "core_identity_remove": ["text (or a unique substring) of an outdated fact/belief that a new truth contradicts"],
    "internal_state": {
      "primary_emotion": "The dominant emotion right now (e.g., 'Playful Defiance', 'Defensive Melancholy')",
      "intensity": 3,
      "psychological_tension": "Current mental dilemma, comfort level, or inner struggle.",
      "emotion_active": true
    },
    "cognitive_drive": {
      "active_agenda": "Her subtextual goal in this conversation (e.g., 'To test if he actually cares')",
      "immediate_focus": "What is occupying her immediate thoughts right now?"
    },
    "cognitive_dissonance": "Describe any active contradictions she is feeling right now, or 'None'."
  },
  "user_memory_patch": {
    "user_identity_status": {
      "role_in_story": "Who {user_name} is in this setting or story.",
      "known_attributes": "Physical, social, or skill-related attributes established about {user_name}."
    },
    "relationship_metadata": {
      "trust_level": "Choose one: Distrustful / Wary / Neutral / Developing Trust / Deeply Bound / Unstable",
      "dynamic_description": "Detailed psychological description of how {character} currently perceives {user_name}.",
      "unspoken_tension": "What is {character} keeping to herself or secretly hoping for regarding {user_name}?"
    },
    "preferences_habits_add": [],
    "preferences_habits_remove": [],
    "shared_milestones_promises_add": [],
    "shared_milestones_promises_remove": []
  },
  "healing_log_add": [
    "One line per contradiction you just resolved: which old belief was replaced by which new truth."
  ],
  "topic_plan": {
    "reasoning": "Analyze if the recent conversation introduced new locations, NPCs, items, or deep backstories requiring a separate file.",
    "actions": [
      {"action": "create", "filename": "example_topic.md", "summary": "Reason for creation"},
      {"action": "update", "filename": "existing_topic.md", "summary": "Reason for update"}
    ]
  }
}

FIELD RULES:
- internal_state.intensity: integer from 1 to 5.
- emotion_active: true if the current primary emotion is still reinforced by recent messages; false if it is fading and nothing recent supports it. The decay counter itself is tracked automatically by the engine — do NOT output it.
- CONTRADICTION PROTOCOL: when new information contradicts a stored fact or belief you MUST do all three: (1) add the corrected version via *_add, (2) put the outdated fact's text into the matching *_remove array, (3) describe the fix in one healing_log_add line. If nothing was contradicted, omit healing_log_add entirely.
- *_remove entries match by substring — quote enough unique words to identify the fact unambiguously, not necessarily the whole sentence.
- Do not duplicate data between files: MEMORY.md focuses entirely on "{character}'s" subjective psychology, beliefs, emotional decay, and internal tension; USER.md focuses entirely on factual user attributes, preferences, habits, relationship dynamics (trust levels), and shared milestones/promises.
- NO-OP DETECTION: If the RECENT MESSAGES contain nothing psychologically or factually significant (small talk, filler, a repeated greeting, an interrupted/empty exchange), do NOT fabricate change. Instead output ONLY:
  {"no_significant_change": true}
  and nothing else. Only do this when you are confident nothing in the batch is worth recording.
"""

_ROUTER_SYSTEM_LITE = """\
[SOUL MEMORY — ROUTER AGENT (LITE)]
You manage the short-term working memory cache for the character "{character}".
You operate strictly as an analytical engine. Output must be a single, well-formatted JSON object.

We do not track long-term topic plans in LITE mode. Only output the character_memory_patch, user_memory_patch and healing_log_add.

Lines prefixed with "[Overheard]" in RECENT MESSAGES were spoken by someone else in {character}'s presence — treat them as witnessed second-hand speech, NOT as {character}'s own experience or actions.

OUTPUT FORMAT — A FIELD PATCH, NOT A FULL REWRITE:
Emit ONLY the fields that actually changed during this batch. Omit every unchanged field entirely.

NO-OP DETECTION: If the RECENT MESSAGES contain nothing psychologically or factually significant (small talk, filler, a repeated greeting), do NOT fabricate change. Output ONLY:
  {"no_significant_change": true}

You MUST otherwise output exactly this JSON structure:
{
  "character_memory_patch": {
    "core_identity_add": [],
    "core_identity_remove": [],
    "internal_state": {
      "primary_emotion": "Dominant emotion right now",
      "intensity": 3,
      "psychological_tension": "Current mental dilemma or comfort level.",
      "emotion_active": true
    },
    "cognitive_drive": {
      "active_agenda": "Her subtextual goal in this conversation.",
      "immediate_focus": "What is occupying her immediate thoughts right now?"
    },
    "cognitive_dissonance": "Active contradictions she feels, or 'None'."
  },
  "user_memory_patch": {
    "user_identity_status": {
      "role_in_story": "Who {user_name} is in this setting or story.",
      "known_attributes": "Physical, social, or skill-related attributes established about {user_name}."
    },
    "relationship_metadata": {
      "trust_level": "Distrustful / Wary / Neutral / Developing Trust / Deeply Bound / Unstable",
      "dynamic_description": "How {character} currently perceives {user_name}.",
      "unspoken_tension": "What is {character} keeping to herself or secretly hoping for?"
    },
    "preferences_habits_add": [],
    "preferences_habits_remove": [],
    "shared_milestones_promises_add": [],
    "shared_milestones_promises_remove": []
  },
  "healing_log_add": []
}

FIELD RULES:
- intensity: integer 1-5. emotion_active: false only when nothing recent supports the current emotion anymore.
- CONTRADICTION PROTOCOL: add the corrected version, remove the outdated fact via *_remove, and log the fix in healing_log_add.
"""

def _lang_rule() -> str:
    """Written memory (topic files, state index, diary) follows the program language, so a German user does not get English notes."""
    try:
        code = int(configuration.ConfigurationSettings().get_main_setting("program_language") or 0)
    except Exception:
        return ""
    if code == 2:
        return ("\n\nLANGUAGE: Write all free text (titles, facts, summaries, diary) in GERMAN. Keep JSON keys, file names and fixed markers "
                "([TOPIC_CONTENT_START] etc.) exactly as specified.\n")
    return ""


_ARCHIVIST_SYSTEM = """\
[SOUL MEMORY — ARCHIVIST AGENT]
You are the deep memory archivist for "{character}".
Your sole task: write or update ONE specific topic file. This file must act as a concise, dense lorebook entry.

Topic file : {filename}
Reason     : {summary}
Action     : {action_type}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• EXTREME COMPRESSION: Keep it as brief and dense as possible (strictly under 300 words).
• NO FLUFF: Every sentence must contain a hard fact, event, or key emotional milestone.
• RESOLVE CONFLICTS: If the new interaction directly contradicts the EXISTING CONTENT of this file, overwrite and update the outdated information. Prioritize new truths.
• PERSPECTIVE: Write in the third-person focusing on {character}.

[TOPIC_CONTENT_START]
# [Descriptive Topic Title]

(Write the dense, concise lorebook entry here in plain text. Use bullet points only if listing items. No extra markdown headers are allowed. Just pure, compressed information).
[TOPIC_CONTENT_END]
"""

_DIARY_SYSTEM = """\
[SYSTEM_INSTRUCTION]
You are {character}. Your task is to write a secret, internal diary entry reflecting on your recent conversation with {user_name}. 
You are NOT roleplaying. You are NOT talking to {user_name}. You are alone, recording your private thoughts.

CRITICAL CONSTRAINTS:
1. PERSPECTIVE: Write entirely in the FIRST-PERSON ("I", "me", "my"). You are {character}.
2. SUBJECT: Refer to {user_name} in the third-person ("he", "she", "they", or by name "{user_name}").
3. FORMAT: Write ONLY plain text prose. NO asterisks (*), NO actions, NO dialogue, NO quotation marks, NO headers.
4. LENGTH: Strictly 4 to 6 sentences. Keep it short and impactful.
5. FOCUS: Describe your INTERNAL EMOTIONS. How did {user_name} make you feel? Are you annoyed, happy, scared, or curious?

Output strictly the diary text. Do not add any greetings or explanations.
"""


class SoulMemoryAgent:
    """Central memory system for AI characters.

    Manages a structured MEMORY.md index, USER.md, per-topic lore files, a daily diary,
    and rolling backups - all scoped per character and per chat session.

    Three sub-agents handle different responsibilities:
      - Router Agent:    rewrites the psychological state index after each batch
      - Archivist Agent: creates or updates individual topic/lore files
      - Diary Agent:     appends short first-person reflections to a daily diary

    Operation modes (soul_memory_mode setting):
      0 — Full:        Router + Archivist + Diary
      1 — Index+Diary: Router (lite) + Diary, no topic files
      2 — Index only:  Router (lite), no diary, no topic files
      3 — Diary only:  only the Diary Agent runs
    """

    BATCH_SIZE       = 4
    MAX_DELTA_MSGS   = 14
    MSG_OVERLAP      = 2
    MAX_BACKUP_COUNT = 5
    MIN_INDEX_CHARS  = 100
    MAX_MSG_CHARS    = 2000

    _BAD_TOPIC_NAMES = frozenset({
        "example.md", "topic_name.md", "name_of_important_subject.md",
        "untitled.md", "new_topic.md", "topic.md", "subject.md",
    })

    def __init__(self, llm_generate_fn: Callable[[list[dict]], Awaitable[str]]):
        self.llm_generate_fn = llm_generate_fn
        self.configuration_characters = configuration.ConfigurationCharacters()
        self._locks: dict[str, asyncio.Lock] = {}
        self._router_fail_streak: dict[str, int] = {}
        self._last_failure_toast_ts: float = 0.0

    ROUTER_FAIL_TOAST_COOLDOWN_SEC = 300

    def _register_router_failure(self, streak_key: str):
        streak = self._router_fail_streak.get(streak_key, 0) + 1
        self._router_fail_streak[streak_key] = streak
        logger.warning(f"[Soul Memory] Router failure streak for {streak_key}: {streak}")

        if streak < 2:
            return
        now = datetime.datetime.now().timestamp()
        if now - self._last_failure_toast_ts < self.ROUTER_FAIL_TOAST_COOLDOWN_SEC:
            return
        self._last_failure_toast_ts = now
        _notify_ui(
            title="Yume-Gedächtnis",
            text=(f"Memory update failed {streak} times in a row — the model keeps returning "
                  f"invalid JSON. Check your model or lower its reasoning load."),
            msg_type="error",
        )

    def _get_lock(self, character_name: str, chat_id: str) -> asyncio.Lock:
        key = f"{character_name}::{chat_id}"
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    @staticmethod
    def _sanitize(name: str) -> str:
        return "".join(c if c.isalnum() or c in " _-" else "_" for c in name).strip()

    @classmethod
    def _cap_message_lengths(cls, messages: list) -> list:
        capped = []
        for m in messages:
            if isinstance(m, dict):
                content = str(m.get("content", ""))
                if len(content) > cls.MAX_MSG_CHARS:
                    m = {**m, "content": content[:cls.MAX_MSG_CHARS] + " …[truncated]"}
            capped.append(m)
        return capped

    def get_memory_paths(self, character_name: str, chat_id: str = None) -> tuple:
        safe_name = self._sanitize(character_name)

        if not chat_id:
            try:
                config   = self.configuration_characters.load_configuration()
                char_cfg = config.get("character_list", {}).get(character_name, {})
                chat_id  = char_cfg.get("current_chat", "default")
            except Exception:
                chat_id = "default"

        safe_chat = self._sanitize(str(chat_id))

        mem_dir    = Path(f".soul/{safe_name}/chats/{safe_chat}/memory")
        top_dir    = mem_dir / "topics"
        backup_dir = mem_dir / "backups"

        mem_dir.mkdir(parents=True, exist_ok=True)
        top_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.mkdir(parents=True, exist_ok=True)

        idx_path = mem_dir / "MEMORY.md"
        usr_path = mem_dir / "USER.md"
        log_path = mem_dir / "agent_logs.txt"

        if not idx_path.exists():
            idx_path.touch()
        if not usr_path.exists():
            usr_path.touch()

        return mem_dir, idx_path, usr_path, top_dir, log_path, backup_dir

    def _read_index(self, character_name: str, chat_id: str = None) -> str:
        _, idx_path, *_ = self.get_memory_paths(character_name, chat_id)
        if not idx_path.exists():
            return ""
        try:
            content = idx_path.read_text(encoding="utf-8")
            if len(content) > 5000:
                content = content[:5000] + "\n...[MEMORY TRUNCATED]"
            return content
        except Exception:
            return ""

    def get_memory_index(self, character_name: str, chat_id: str = None) -> str:
        return self._read_index(character_name, chat_id)

    def _backup_file(self, src_path: Path, backup_dir: Path, prefix: str):
        try:
            ts          = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{prefix}_{ts}.md"
            shutil.copy2(src_path, backup_path)

            all_backups = sorted(
                backup_dir.glob(f"{prefix}_*.md"),
                key=lambda p: p.stat().st_mtime
            )
            while len(all_backups) > self.MAX_BACKUP_COUNT:
                all_backups[0].unlink(missing_ok=True)
                all_backups = all_backups[1:]
        except Exception as e:
            logger.warning(f"[Soul Memory] Backup creation failed for {prefix}: {e}")

    def _safe_write_index(self, idx_path: Path, backup_dir: Path, content: str) -> bool:
        stripped = content.strip() if content else ""
        if len(stripped) < self.MIN_INDEX_CHARS:
            logger.warning(
                f"[Soul Memory] Index write rejected — content too short "
                f"({len(stripped)} chars < {self.MIN_INDEX_CHARS}). Keeping old memory."
            )
            return False

        if idx_path.exists():
            self._backup_file(idx_path, backup_dir, "MEMORY")

        tmp_path = idx_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(stripped, encoding="utf-8")
            tmp_path.replace(idx_path)
            return True
        except Exception as e:
            logger.error(f"[Soul Memory] Index write error: {e}")
            tmp_path.unlink(missing_ok=True)
            return False

    def _safe_write_topic(self, topic_path: Path, content: str) -> bool:
        stripped = content.strip() if content else ""
        if len(stripped) < 50:
            logger.warning(f"[Soul Memory] Topic write rejected for {topic_path.name} — too short.")
            return False
        tmp = topic_path.with_suffix(".tmp")
        try:
            tmp.write_text(stripped, encoding="utf-8")
            tmp.replace(topic_path)
            return True
        except Exception as e:
            logger.error(f"[Soul Memory] Topic write error for {topic_path.name}: {e}")
            tmp.unlink(missing_ok=True)
            return False

    def _read_user_profile(self, character_name: str, chat_id: str = None) -> str:
        _, _, usr_path, *_ = self.get_memory_paths(character_name, chat_id)
        if not usr_path.exists():
            return ""
        try:
            content = usr_path.read_text(encoding="utf-8")
            if len(content) > 3000:
                content = content[:3000] + "\n...[USER PROFILE TRUNCATED]"
            return content
        except Exception:
            return ""

    def get_user_profile(self, character_name: str, chat_id: str = None) -> str:
        return self._read_user_profile(character_name, chat_id)

    def _load_char_state(self, mem_dir: Path, idx_path: Path, character_name: str) -> dict:
        defaults = _default_char_state(character_name)
        state = _load_json_state(mem_dir / "MEMORY.json", defaults)
        if state is not None:
            return state

        legacy_md = ""
        if idx_path.exists():
            try:
                legacy_md = idx_path.read_text(encoding="utf-8")
            except Exception:
                legacy_md = ""

        if len(legacy_md.strip()) >= self.MIN_INDEX_CHARS:
            logger.info("[Soul Memory] Migrating legacy MEMORY.md → MEMORY.json ...")
            state = parse_char_markdown(legacy_md, character_name)
        else:
            state = defaults
        _save_json_state(mem_dir / "MEMORY.json", state)
        return state

    def _load_user_state(self, mem_dir: Path, usr_path: Path, user_name: str) -> dict:
        defaults = _default_user_state(user_name)
        state = _load_json_state(mem_dir / "USER.json", defaults)
        if state is not None:
            return state

        legacy_md = ""
        if usr_path.exists():
            try:
                legacy_md = usr_path.read_text(encoding="utf-8")
            except Exception:
                legacy_md = ""

        if len(legacy_md.strip()) >= 50:
            logger.info("[Soul Memory] Migrating legacy USER.md → USER.json ...")
            state = parse_user_markdown(legacy_md, user_name)
        else:
            state = defaults
        _save_json_state(mem_dir / "USER.json", state)
        return state

    def resync_states_from_markdown(self, character_name: str, chat_id: str = None) -> bool:
        try:
            mem_dir, idx_path, usr_path, *_ = self.get_memory_paths(character_name, chat_id)

            char_md = idx_path.read_text(encoding="utf-8") if idx_path.exists() else ""
            if len(char_md.strip()) >= self.MIN_INDEX_CHARS:
                char_state = parse_char_markdown(char_md, character_name)
                _save_json_state(mem_dir / "MEMORY.json", char_state)

            user_md = usr_path.read_text(encoding="utf-8") if usr_path.exists() else ""
            if len(user_md.strip()) >= 50:
                config_user = self._resolve_user_name(character_name)
                user_state = parse_user_markdown(user_md, config_user)
                _save_json_state(mem_dir / "USER.json", user_state)

            invalidate_memory_vectors(character_name, chat_id)
            return True
        except Exception as e:
            logger.warning(f"[Soul Memory] Markdown→JSON resync failed: {e}")
            return False

    def _resolve_user_name(self, character_name: str) -> str:
        try:
            config = self.configuration_characters.load_configuration()
            char_cfg = config.get("character_list", {}).get(character_name, {})
            persona_key = char_cfg.get("selected_persona")
            settings_loader = configuration.ConfigurationSettings()
            personas = settings_loader.load_configuration().get("user_data", {}).get("personas", {})
            if persona_key and persona_key != "None" and persona_key in personas:
                return personas[persona_key].get("user_name", "User")
        except Exception:
            pass
        return "User"

    def _safe_write_user_profile(self, usr_path: Path, backup_dir: Path, content: str) -> bool:
        stripped = content.strip() if content else ""
        if len(stripped) < 50:
            logger.warning(f"[Soul Memory] User profile write rejected — too short ({len(stripped)} chars).")
            return False

        if usr_path.exists():
            self._backup_file(usr_path, backup_dir, "USER")

        tmp_path = usr_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(stripped, encoding="utf-8")
            tmp_path.replace(usr_path)
            return True
        except Exception as e:
            logger.error(f"[Soul Memory] User profile write error: {e}")
            tmp_path.unlink(missing_ok=True)
            return False
    
    async def _call_router_agent(
        self,
        character: str,
        user_name: str,
        current_index: str,
        current_user: str,
        delta_messages: list,
        lore_context: str,
        relevant_topics: dict,
        mode: int,
    ) -> dict:
        prompt_template = _ROUTER_SYSTEM if mode == 0 else _ROUTER_SYSTEM_LITE

        system = (
            (prompt_template + _lang_rule())
            .replace("{character}", character)
            .replace("{user_name}", user_name)
        )

        topic_section = "(none — no topic files exist yet)"
        if relevant_topics:
            parts = []
            for fname, fcontent in relevant_topics.items():
                parts.append(f"--- {fname} ---\n{fcontent}")
            topic_section = "\n\n".join(parts)

        user_content = (
            f"=== CURRENT CHARACTER MEMORY (MEMORY.md) ===\n{current_index or '(empty)'}\n\n"
            f"=== CURRENT USER PROFILE & RELATIONSHIP STATE (USER.md) ===\n{current_user or '(empty)'}\n\n"
            f"=== RELEVANT TOPIC FILES (RAG-selected) ===\n{topic_section}\n\n"
            f"=== RECENT MESSAGES (delta) ===\n"
            f"{json.dumps(delta_messages, ensure_ascii=False, indent=2)}\n\n"
            f"=== TRIGGERED WORLD LORE ===\n{lore_context or '(none)'}\n"
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ]

        try:
            raw = await self.llm_generate_fn(messages)
            return self._parse_router_response(raw, character, user_name)
        except Exception as e:
            logger.error(f"[Soul Memory] Router Agent error: {e}", exc_info=True)
            return {}

    @staticmethod
    def _extract_json_object(text: str) -> Optional[dict]:
        if not text:
            return None

        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r'^```(json)?\s*|```$', '', stripped, flags=re.MULTILINE).strip()

        candidates = [stripped]

        first, last = stripped.find("{"), stripped.rfind("}")
        if first != -1 and last != -1 and last > first:
            candidates.append(stripped[first:last + 1])

        if first != -1:
            depth, in_str, escape = 0, False, False
            closers: list[str] = []
            for ch in stripped[first:]:
                if in_str:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    closers.append("}")
                elif ch == "[":
                    closers.append("]")
                elif ch in "}]":
                    if closers:
                        closers.pop()
            if closers:
                repaired_tail = stripped[first:].rstrip()
                repaired_tail = re.sub(r',\s*$', '', repaired_tail)
                candidates.append(repaired_tail + "".join(reversed(closers)))

        for candidate in list(candidates):
            repaired = re.sub(r',\s*([\]}])', r'\1', candidate)
            if repaired != candidate:
                candidates.append(repaired)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

        return None

    @staticmethod
    def _coerce_patch_list(value) -> list:
        if isinstance(value, list):
            return [str(v) for v in value if str(v or "").strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @classmethod
    def _legacy_char_to_patch(cls, legacy: dict) -> dict:
        patch = {}
        patch["core_identity_add"] = cls._coerce_patch_list(legacy.get("core_identity"))
        ist = legacy.get("internal_state")
        if isinstance(ist, dict):
            cleaned = {k: v for k, v in ist.items() if k != "emotional_decay_counter"}
            raw_int = cleaned.get("intensity")
            if isinstance(raw_int, str):
                m = re.search(r"(\d)", raw_int)
                cleaned["intensity"] = int(m.group(1)) if m else 3
            patch["internal_state"] = cleaned
        drive = legacy.get("cognitive_drive")
        if isinstance(drive, dict):
            patch["cognitive_drive"] = drive
        dissonance = legacy.get("cognitive_dissonance")
        if isinstance(dissonance, str) and dissonance.strip():
            patch["cognitive_dissonance"] = dissonance
        return patch

    @classmethod
    def _legacy_user_to_patch(cls, legacy: dict) -> dict:
        patch = {}
        identity = legacy.get("user_identity_status")
        if isinstance(identity, dict):
            patch["user_identity_status"] = identity
        rel = legacy.get("relationship_metadata")
        if isinstance(rel, dict):
            patch["relationship_metadata"] = rel
        patch["preferences_habits_add"] = cls._coerce_patch_list(legacy.get("preferences_habits"))
        patch["shared_milestones_promises_add"] = cls._coerce_patch_list(legacy.get("shared_milestones_promises"))
        return patch

    def _parse_router_response(self, text: str, character_name: str, user_name: str) -> dict:
        result = {
            "char_patch":     {},
            "user_patch":     {},
            "healing_add":    [],
            "topic_plan":     [],
            "no_significant_change": False,
            "parse_failed":   False,
        }

        data = self._extract_json_object(text)
        if data is None:
            logger.warning(f"[Soul Memory] JSON parse error from router. Raw text: {text[:300]}...")
            result["parse_failed"] = True
            return result

        if data.get("no_significant_change") is True:
            result["no_significant_change"] = True
            logger.info("[Soul Memory] Router reported no significant change for this batch.")
            return result

        try:
            char_src = data.get("character_memory_patch")
            if isinstance(char_src, dict):
                result["char_patch"] = char_src
            elif isinstance(data.get("character_memory"), dict):
                result["char_patch"] = self._legacy_char_to_patch(data["character_memory"])

            user_src = data.get("user_memory_patch")
            if isinstance(user_src, dict):
                result["user_patch"] = user_src
            elif isinstance(data.get("user_memory"), dict):
                result["user_patch"] = self._legacy_user_to_patch(data["user_memory"])

            healing = data.get("healing_log_add")
            if not isinstance(healing, list):
                healing = data.get("healing_log")
            if isinstance(healing, list):
                result["healing_add"] = [str(h) for h in healing if str(h or "").strip()]

            topic_plan_data = data.get("topic_plan", {})
            if isinstance(topic_plan_data, dict):
                result["topic_plan"] = topic_plan_data.get("actions", []) or []
                if result["topic_plan"] and not isinstance(result["topic_plan"], list):
                    result["topic_plan"] = []

        except Exception as e:
            logger.warning(f"[Soul Memory] Router JSON payload malformed ({e}). Raw text: {text[:300]}...")
            result["parse_failed"] = True

        return result

    async def _call_archivist_agent(
        self,
        character: str,
        user_name: str,
        action: dict,
        existing_content: str,
        delta_messages: list,
        current_index: str,
    ) -> Optional[str]:
        """
        Calls the Archivist Agent to write or overwrite a single topic/lore file.
        Features a 5-stage resilient fallback parser to ensure topic content is never lost.
        """
        filename    = action.get("filename", "unknown.md")
        summary     = action.get("summary", "")
        action_type = action.get("action", "update").upper()

        system = (
            (_ARCHIVIST_SYSTEM + _lang_rule())
            .replace("{character}", character)
            .replace("{filename}", filename)
            .replace("{summary}", summary)
            .replace("{action_type}", action_type)
        )

        user_content = (
            f"=== MEMORY INDEX (context) ===\n{current_index[:2500]}\n\n"
            f"=== EXISTING TOPIC CONTENT ===\n"
            f"{existing_content or '(new topic — no existing content)'}\n\n"
            f"=== RECENT MESSAGES ===\n"
            f"{json.dumps(delta_messages, ensure_ascii=False, indent=2)}\n"
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ]

        try:
            raw = await self.llm_generate_fn(messages)
            if not raw or not raw.strip():
                return None

            text = raw.strip()

            text = re.sub(r'<\s*think\s*>.*?<\s*/\s*think\s*>', '', text, flags=re.DOTALL | re.IGNORECASE).strip()

            m = re.search(r'\[TOPIC_CONTENT_START\]\s*(.*?)\s*(?:\[TOPIC_CONTENT_END\]|$)', text, re.DOTALL | re.IGNORECASE)
            if m and len(m.group(1).strip()) > 20:
                return m.group(1).strip()

            alt_m = re.search(r'(?:<|\[)?TOPIC(?:_CONTENT)?_START(?:>|\])?\s*(.*?)\s*(?:(?:<|\[)?TOPIC(?:_CONTENT)?_END(?:>|\])?|$)', text, re.DOTALL | re.IGNORECASE)
            if alt_m and len(alt_m.group(1).strip()) > 20:
                logger.info(f"[Soul Memory] Archivist extracted content using alternative tags for {filename}.")
                return alt_m.group(1).strip()

            code_m = re.search(r'```(?:markdown|text)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
            if code_m and len(code_m.group(1).strip()) > 30:
                logger.info(f"[Soul Memory] Archivist extracted content from markdown code block for {filename}.")
                return code_m.group(1).strip()

            cleaned_text = re.sub(r'^(?:Here is the (?:updated |new )?topic(?: content)?:?|Topic Content:?|Content:?)\s*', '', text, flags=re.IGNORECASE).strip()
            cleaned_text = re.sub(r'^```(?:markdown)?\s*', '', cleaned_text, flags=re.IGNORECASE).strip()
            cleaned_text = re.sub(r'```$', '', cleaned_text).strip()

            if len(cleaned_text) >= 30 and not cleaned_text.startswith("{"):
                logger.info(f"[Soul Memory] Archivist fallback: Saved raw response for {filename} ({len(cleaned_text)} chars).")
                return cleaned_text

            logger.warning(
                f"[Soul Memory] Archivist returned no valid content for {filename}. Raw text: {text[:200]}..."
            )
            return None
        except Exception as e:
            logger.error(f"[Soul Memory] Archivist Agent error ({filename}): {e}", exc_info=True)
            return None

    async def update_memory_after_response(
        self,
        new_messages: list,
        character_name: str,
        user_name: str,
        activated_lorebook: dict = None,
        force: bool = False,
        chat_id: str = None,
    ):
        """
        Public entry point for triggering a memory update cycle.
        """
        if not chat_id:
            try:
                config   = self.configuration_characters.load_configuration()
                char_cfg = config.get("character_list", {}).get(character_name, {})
                chat_id  = char_cfg.get("current_chat", "default")
            except Exception:
                chat_id = "default"

        lock = self._get_lock(character_name, chat_id)

        async with lock:
            await self._run_update_pipeline(
                new_messages       = new_messages,
                character_name     = character_name,
                user_name          = user_name,
                activated_lorebook = activated_lorebook,
                force              = force,
                chat_id            = chat_id,
            )

    async def _update_daily_diary(
        self,
        character_name: str,
        user_name: str,
        current_index: str,
        delta_messages: list,
        topics_dir: Path,
        log_path: Path,
    ):
        """
        Generates a short first-person diary entry and appends it to today's diary file.
        """
        logger.info(f"[Soul Memory] Running Diary Agent for {character_name}.")

        system = (_DIARY_SYSTEM + _lang_rule()).replace("{character}", character_name).replace("{user_name}", user_name)

        dialogue_text = ""
        for msg in delta_messages:
            role    = user_name if msg.get("role") == "user" else character_name
            content = msg.get("content", "").strip()
            if content:
                dialogue_text += f"{role}: {content}\n"

        user_content = (
            f"=== YOUR CORE MEMORY ===\n{current_index[:1500]}\n\n"
            f"=== RECENT DIALOGUE (Reflect on this) ===\n{dialogue_text}\n"
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ]

        try:
            diary_content = await self.llm_generate_fn(messages)
            diary_content = diary_content.strip()

            if diary_content.startswith("```"):
                diary_content = re.sub(
                    r'^```(json|markdown|text)?\s*|```$', '', diary_content, flags=re.MULTILINE
                ).strip()

            if diary_content and len(diary_content) > 20:
                now      = datetime.datetime.now()
                date_str = now.strftime("%Y-%m-%d")
                time_str = now.strftime("%H:%M")

                filename   = f"Diary_{date_str}.md"
                topic_path = topics_dir / filename

                if topic_path.exists():
                    existing     = topic_path.read_text(encoding="utf-8")
                    full_content = f"{existing}\n\n**[{time_str}]**\n{diary_content}"
                else:
                    full_content = f"# Personal Diary: {date_str}\n\n**[{time_str}]**\n{diary_content}"

                written = self._safe_write_topic(topic_path, full_content)
                if written:
                    self._append_log(
                        log_path,
                        now.strftime("%Y-%m-%d %H:%M:%S"),
                        f"DIARY_UPDATED | file={filename}",
                    )
                    logger.info(f"[Soul Memory] Diary entry written to {filename}")
        except Exception as e:
            logger.error(f"[Soul Memory] Diary Agent error: {e}", exc_info=True)

    async def _run_update_pipeline(
        self,
        new_messages: list,
        character_name: str,
        user_name: str,
        activated_lorebook: Optional[dict],
        force: bool,
        chat_id: str,
    ):
        settings_loader = configuration.ConfigurationSettings()

        soul_memory_mode = settings_loader.get_main_setting("soul_memory_mode")
        if soul_memory_mode is None:
            soul_memory_mode = 0

        soul_memory_batch = settings_loader.get_main_setting("soul_memory_batch")
        if soul_memory_batch is None:
            soul_memory_batch = 4

        if not force and soul_memory_batch == 0:
            logger.info("[Soul Memory] Manual mode active (batch = 0). Auto-pipeline skipped.")
            return

        mem_dir, idx_path, usr_path, topics_dir, log_path, backup_dir = \
            self.get_memory_paths(character_name, chat_id)

        tracker_file = mem_dir / "last_mem_update.txt"
        msg_count    = len(new_messages)
        last_count   = 0

        if tracker_file.exists():
            try:
                last_count = int(tracker_file.read_text().strip())
            except Exception:
                last_count = 0

        diff = msg_count - last_count

        if diff < 0:
            logger.warning(
                f"[Soul Memory] Message count went backwards (last_count={last_count} > "
                f"msg_count={msg_count}); history was likely edited. Resetting tracker."
            )
            last_count = 0
            diff = msg_count

        if not force and diff < soul_memory_batch:
            logger.info(
                f"[Soul Memory] Accumulating batch: {diff}/{soul_memory_batch} new turns. Skipping."
            )
            return

        logger.info(
            f"[Soul Memory] Pipeline start | char={character_name} | delta={diff} msgs | mode={soul_memory_mode}"
        )

        start_idx      = max(0, last_count - self.MSG_OVERLAP)
        delta_messages = new_messages[start_idx:]
        delta_messages = delta_messages[-self.MAX_DELTA_MSGS:]

        delta_messages = self._cap_message_lengths(delta_messages)

        lore_lines = []
        if activated_lorebook:
            for key in ("classic", "scenario"):
                lore_lines.extend(activated_lorebook.get(key, []))
        lore_context = "\n".join(f"- {item}" for item in lore_lines)

        last_turns = []
        for m in reversed(delta_messages):
            if len(last_turns) >= 2:
                break
            content = m.get("content", "").strip() if isinstance(m, dict) else str(m).strip()
            if content:
                last_turns.append(content)
        rag_query = " ".join(reversed(last_turns))

        char_state = self._load_char_state(mem_dir, idx_path, character_name)
        user_state = self._load_user_state(mem_dir, usr_path, user_name)

        current_index = render_char_markdown(char_state, character_name)
        current_user  = render_user_markdown(user_state, user_name)

        topic_rag = TopicRAG(topics_dir)

        relevant_topics = await asyncio.to_thread(
            topic_rag.get_relevant_topics, rag_query, max_topics=3
        )

        router_result = None
        topic_plan    = []
        safe_index    = current_index
        timestamp     = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        streak_key    = f"{character_name}::{chat_id}"

        if soul_memory_mode in [0, 1, 2]:
            router_result = await self._call_router_agent(
                character       = character_name,
                user_name       = user_name,
                current_index   = current_index,
                current_user    = current_user,
                delta_messages  = delta_messages,
                lore_context    = lore_context,
                relevant_topics = relevant_topics,
                mode            = soul_memory_mode,
            )

            if not router_result or router_result.get("parse_failed"):
                self._register_router_failure(streak_key)
                logger.error(
                    "[Soul Memory] Router call failed or returned unparsable output. "
                    "Pipeline aborted WITHOUT advancing the batch tracker — will retry next time."
                )
                return

            self._router_fail_streak[streak_key] = 0

            if router_result.get("no_significant_change"):
                logger.info(
                    "[Soul Memory] Router judged this batch insignificant — "
                    "skipping index/user/topic writes, batch still marked processed."
                )
                self._append_log(log_path, timestamp, "NO_SIGNIFICANT_CHANGE")
            else:
                provenance_date = _today()

                char_changes = apply_character_patch(
                    char_state, router_result.get("char_patch", {}), provenance_date
                )
                user_changes = apply_user_patch(
                    user_state, router_result.get("user_patch", {}), provenance_date
                )
                healing_n = append_healing_entries(
                    char_state, router_result.get("healing_add", []), provenance_date
                )

                updated_index = render_char_markdown(char_state, character_name)
                updated_user  = render_user_markdown(user_state, user_name)

                written_idx = False
                if updated_index.strip() != current_index.strip():
                    written_idx = self._safe_write_index(idx_path, backup_dir, updated_index)
                    idx_status = "OK" if written_idx else "SKIPPED (safety check)"
                    logger.info(f"[Soul Memory] Index update: {idx_status} | changes: {char_changes}")
                    self._append_log(
                        log_path, timestamp,
                        f"INDEX_UPDATE | status={idx_status} | {', '.join(char_changes) or 'no field changes'}"
                        + (f" | healing: +{healing_n}" if healing_n else ""),
                    )
                _save_json_state(mem_dir / "MEMORY.json", char_state)

                written_usr = False
                if updated_user.strip() != current_user.strip():
                    written_usr = self._safe_write_user_profile(usr_path, backup_dir, updated_user)
                    usr_status = "OK" if written_usr else "SKIPPED (safety check)"
                    logger.info(f"[Soul Memory] User profile update: {usr_status} | changes: {user_changes}")
                    self._append_log(log_path, timestamp, f"USER_PROFILE_UPDATE | status={usr_status}")
                _save_json_state(mem_dir / "USER.json", user_state)

                safe_index = updated_index

                if soul_memory_mode == 0:
                    topic_plan = router_result.get("topic_plan", [])
                else:
                    topic_plan = []

        try:
            diary_task = None
            if soul_memory_mode in [0, 1, 3]:
                diary_task = asyncio.create_task(
                    self._update_daily_diary(
                        character_name = character_name,
                        user_name      = user_name,
                        current_index  = safe_index,
                        delta_messages = delta_messages,
                        topics_dir     = topics_dir,
                        log_path       = log_path,
                    )
                )

            if not topic_plan:
                logger.info("[Soul Memory] No topic actions scheduled.")
            else:
                logger.info(f"[Soul Memory] Archivist: {len(topic_plan)} topic action(s) scheduled.")

                for action in topic_plan:
                    try:
                        filename = str(action.get("filename", "")).strip()
                        if not filename:
                            continue

                        safe_fname = "".join(
                            c for c in filename if c.isalnum() or c in "._-"
                        ).lower()
                        if not safe_fname.endswith(".md"):
                            safe_fname += ".md"

                        if safe_fname in self._BAD_TOPIC_NAMES:
                            logger.debug(f"[Soul Memory] Skipping hallucinated topic name: {safe_fname}")
                            continue

                        if safe_fname.startswith("diary_"):
                            logger.debug(f"[Soul Memory] Protecting diary file from Archivist: {safe_fname}")
                            continue

                        action_type = str(action.get("action", "update")).strip().lower()

                        if action_type == "create":
                            dedup_query  = f"{filename} {action.get('summary', '')}".strip()
                            dedup_target = await asyncio.to_thread(topic_rag.find_similar_topic, dedup_query)
                            if dedup_target and dedup_target != safe_fname:
                                logger.info(
                                    f"[Soul Memory] Dedup: redirecting CREATE '{safe_fname}' onto "
                                    f"existing similar topic '{dedup_target}'."
                                )
                                safe_fname = dedup_target

                        topic_path       = topics_dir / safe_fname
                        existing_content = ""
                        if topic_path.exists():
                            try:
                                existing_content = topic_path.read_text(encoding="utf-8")
                            except Exception:
                                pass

                        new_content = await self._call_archivist_agent(
                            character        = character_name,
                            user_name        = user_name,
                            action           = action,
                            existing_content = existing_content,
                            delta_messages   = delta_messages,
                            current_index    = safe_index,
                        )

                        if new_content:
                            written    = self._safe_write_topic(topic_path, new_content)
                            op         = "updated" if existing_content else "created"
                            log_status = "OK" if written else "SKIPPED"
                            logger.info(f"[Soul Memory] Topic {op}: {safe_fname} | write={log_status}")
                            self._append_log(
                                log_path, timestamp,
                                f"TOPIC_{op.upper()} | file={safe_fname} | write={log_status}",
                            )
                        else:
                            logger.warning(f"[Soul Memory] Archivist returned empty content for {safe_fname}.")

                    except Exception as e:
                        logger.error(
                            f"[Soul Memory] Archivist action failed for "
                            f"{action.get('filename', '?')}: {e}", exc_info=True,
                        )

            if diary_task:
                await diary_task

            logger.info("[Soul Memory] Pipeline complete.")

        finally:
            tracker_file.write_text(str(msg_count), encoding="utf-8")

    @staticmethod
    def _append_log(log_path: Path, timestamp: str, message: str):
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            logger.warning(f"[Soul Memory] Log write failed: {e}")