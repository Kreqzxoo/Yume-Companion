"""Portable backup and backward-compatible restore helpers for Soul of Waifu 2.5.3.

Exports personal configuration, character/chat data and user data without the
Python runtime. Import supports current SoW archives, unmanifested 2.5.1 ZIPs,
and legacy backup folders containing the historical app/configuration layout.
Large optional model files are streamed to disk instead of loaded into RAM.
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
import logging
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

logger = logging.getLogger("SoWBackup")
APP_VERSION = "2.5.3"
BACKUP_FORMAT = "soul-of-waifu-backup"

CONFIG_FILES = {
    "app/configuration/settings.json",
    "app/configuration/api.json",
    "app/configuration/characters.json",
    "app/configuration/branding.json",
}
BASE_DIRS = (
    "app/data/",
    "app/cache/avatars/",
)
OPTIONAL_DIRS = (
    "app/voices/",
    "app/rvc_models/",
    "assets/ambient/",
    "assets/backgrounds/",
    "assets/emotions/",
    "assets/local_llm/",
    "assets/rvc_models/",
    "assets/live2d/",
    "assets/vrm/",
)
MAX_ARCHIVE_ENTRIES = 100_000
MAX_CONFIG_SIZE = 32 * 1024 * 1024


class BackupError(Exception):
    """Raised when a backup cannot safely be read or restored."""


@dataclass(frozen=True)
class _SourceEntry:
    kind: str                     # "zip" or "file"
    source: Path
    member: str | None = None     # ZIP member name for kind="zip"


class BackupManager:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).resolve() if root else Path(__file__).resolve().parents[2]
        self.backup_dir = self.root / "backups"
        self._detected_source_version: str | None = None

    def create_backup(
        self,
        destination: str | Path | None = None,
        include_assets: bool = False,
        label: str = "manual",
        additional_paths: list[str] | None = None,
    ) -> tuple[Path, dict[str, Any]]:
        """Create a portable ZIP backup and its manifest. Returns (path, summary)."""
        now = _dt.datetime.now().astimezone()
        stamp = now.strftime("%Y%m%d-%H%M%S")
        if destination:
            out = Path(destination).expanduser().resolve()
        else:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            out = self.backup_dir / f"Soul-of-Waifu-{label}-Backup-{stamp}.zip"
        out.parent.mkdir(parents=True, exist_ok=True)

        wanted = set(CONFIG_FILES)
        wanted.update(BASE_DIRS)
        if include_assets:
            wanted.update(OPTIONAL_DIRS)
        for rel in additional_paths or []:
            normalized = self._normalize_relative(rel)
            if normalized and self._is_allowed(normalized):
                wanted.add(normalized)

        files: list[tuple[Path, str]] = []
        for entry in sorted(wanted):
            src = self.root / entry.rstrip("/")
            if entry.endswith("/"):
                if src.is_dir():
                    for item in src.rglob("*"):
                        if item.is_file() and not self._skip_file(item):
                            rel = item.relative_to(self.root).as_posix()
                            if self._is_allowed(rel):
                                files.append((item, rel))
            elif src.is_file() and not self._skip_file(src):
                files.append((src, entry))

        unique: dict[str, Path] = {rel: src for src, rel in files}
        files = [(src, rel) for rel, src in sorted(unique.items())]
        manifest = {
            "format": BACKUP_FORMAT,
            "format_version": 1,
            "app_version": APP_VERSION,
            "created_at": now.isoformat(timespec="seconds"),
            "include_assets": bool(include_assets),
            "files": [rel for _, rel in files],
            "note": "Contains personal settings, API tokens, characters and user data. Keep it private.",
        }
        try:
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                archive.writestr("metadata/manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
                for src, rel in files:
                    archive.write(src, rel)
        except Exception:
            try:
                out.unlink(missing_ok=True)
            except Exception:
                pass
            raise
        return out, {"version": APP_VERSION, "files": len(files), "include_assets": include_assets}

    def inspect_backup(self, source: str | Path) -> dict[str, Any]:
        """Inspect an archive/folder and validate any included configuration JSON."""
        src = Path(source).expanduser().resolve()
        entries, configs = self._scan_source(src)
        self._validate_payload(configs, entries.keys())
        return {
            "source": str(src),
            "source_version": self._detect_version(configs),
            "files": sorted(entries.keys()),
            "file_count": len(entries),
        }

    def restore_backup(self, source: str | Path) -> dict[str, Any]:
        """Restore current or legacy backup with automatic pre-restore safety backup."""
        src = Path(source).expanduser().resolve()
        entries, configs = self._scan_source(src)
        self._validate_payload(configs, entries.keys())
        source_version = self._detect_version(configs)

        if "app/configuration/settings.json" in configs:
            configs["app/configuration/settings.json"] = self._migrate_settings(
                configs["app/configuration/settings.json"]
            )

        # Snapshot exactly the user-data paths the archive may change, plus the
        # default settings/configuration/memory set. Files are streamed by zipfile.
        before, before_info = self.create_backup(
            include_assets=False,
            label="before-restore",
            additional_paths=[p for p in entries if not p.startswith("app/configuration/")],
        )

        restored: list[str] = []
        with tempfile.TemporaryDirectory(prefix="sow_restore_stage_") as temp_dir:
            stage = Path(temp_dir)
            # Stage and verify every byte before touching the live installation.
            archive_context = zipfile.ZipFile(src, "r") if src.is_file() else None
            try:
                for rel, entry in entries.items():
                    target_stage = stage / rel
                    target_stage.parent.mkdir(parents=True, exist_ok=True)
                    if rel in CONFIG_FILES:
                        target_stage.write_bytes(configs[rel])
                    elif entry.kind == "file":
                        shutil.copyfile(entry.source, target_stage)
                    else:
                        assert archive_context is not None and entry.member is not None
                        try:
                            with archive_context.open(entry.member, "r") as source_stream, target_stage.open("wb") as out_stream:
                                shutil.copyfileobj(source_stream, out_stream, length=1024 * 1024)
                        except Exception as exc:
                            raise BackupError(f"Datei konnte nicht vollständig aus dem Backup gelesen werden ({rel}): {exc}") from exc
            finally:
                if archive_context is not None:
                    archive_context.close()

            # Apply staged files using atomic replacement where possible.
            for rel in sorted(entries):
                dest = (self.root / rel).resolve()
                if not self._is_inside_root(dest):
                    raise BackupError(f"Unsicherer Zielpfad: {rel}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists() and dest.is_dir():
                    raise BackupError(f"Kann eine Datei nicht über einen vorhandenen Ordner schreiben: {rel}")
                staged = stage / rel
                tmp_dest = dest.with_name(dest.name + ".sowtmp")
                try:
                    shutil.copyfile(staged, tmp_dest)
                    if dest.exists():
                        shutil.copystat(dest, tmp_dest, follow_symlinks=True)
                    os.replace(tmp_dest, dest)
                finally:
                    try:
                        tmp_dest.unlink(missing_ok=True)
                    except OSError:
                        pass
                restored.append(rel)

        return {
            "source_version": source_version,
            "files_restored": len(restored),
            "restored_paths": restored,
            "automatic_backup": str(before),
            "automatic_backup_files": before_info.get("files", 0),
        }

    def _scan_source(self, source: Path) -> tuple[dict[str, _SourceEntry], dict[str, bytes]]:
        """Index files on disk; load only small JSON config files into RAM."""
        self._detected_source_version = None
        entries: dict[str, _SourceEntry] = {}
        configs: dict[str, bytes] = {}
        if source.is_dir():
            self._read_folder_manifest(source)
            file_count = 0
            for item in source.rglob("*"):
                if not item.is_file() or self._skip_file(item):
                    continue
                file_count += 1
                if file_count > MAX_ARCHIVE_ENTRIES:
                    raise BackupError(f"Der Backup-Ordner enthält mehr als {MAX_ARCHIVE_ENTRIES} Dateien.")
                rel_src = item.relative_to(source).as_posix()
                rel = self._normalise_archive_entry(rel_src)
                if not rel or not self._is_allowed(rel):
                    continue
                entries[rel] = _SourceEntry("file", item)
                if rel in CONFIG_FILES:
                    if item.stat().st_size > MAX_CONFIG_SIZE:
                        raise BackupError(f"Konfigurationsdatei ist ungewöhnlich groß: {rel}")
                    configs[rel] = item.read_bytes()
            return entries, configs

        if not source.is_file():
            raise BackupError("Die ausgewählte Backup-Datei bzw. der Backup-Ordner existiert nicht.")
        if not zipfile.is_zipfile(source):
            raise BackupError("Das Backup ist kein ZIP-Archiv. Unterstützt werden ZIP-/SOW-Backups und alte Backup-Ordner.")

        try:
            with zipfile.ZipFile(source, "r") as archive:
                infos = archive.infolist()
                if len(infos) > MAX_ARCHIVE_ENTRIES:
                    raise BackupError(f"Das Archiv enthält zu viele Einträge ({len(infos)}).")
                for manifest_name in ("metadata/manifest.json", "manifest.json"):
                    try:
                        manifest_obj = json.loads(archive.read(manifest_name).decode("utf-8-sig"))
                        if isinstance(manifest_obj, dict):
                            self._detected_source_version = str(manifest_obj.get("app_version") or manifest_obj.get("version") or "unbekannt")
                        break
                    except (KeyError, ValueError, UnicodeDecodeError):
                        continue
                for info in infos:
                    if info.is_dir():
                        continue
                    if PurePosixPath(info.filename.replace("\\", "/")).name in {".gitkeep", ".DS_Store", "Thumbs.db"}:
                        continue
                    raw = info.filename.replace("\\", "/")
                    pp = PurePosixPath(raw)
                    if pp.is_absolute() or any(part == ".." for part in pp.parts):
                        logger.warning("Skipping unsafe backup entry %r", info.filename)
                        continue
                    rel = self._normalise_archive_entry(raw)
                    if not rel or not self._is_allowed(rel):
                        continue
                    entries[rel] = _SourceEntry("zip", source, info.filename)
                    if rel in CONFIG_FILES:
                        if info.file_size > MAX_CONFIG_SIZE:
                            raise BackupError(f"Konfigurationsdatei ist ungewöhnlich groß: {rel}")
                        configs[rel] = archive.read(info)
        except zipfile.BadZipFile as exc:
            raise BackupError(f"Das Backup-ZIP ist beschädigt: {exc}") from exc
        return entries, configs

    def _read_folder_manifest(self, folder: Path) -> None:
        for manifest_path in (folder / "metadata" / "manifest.json", folder / "manifest.json"):
            if not manifest_path.is_file():
                continue
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    self._detected_source_version = str(data.get("app_version") or data.get("version") or "unbekannt")
            except Exception:
                logger.warning("Could not read backup manifest: %s", manifest_path, exc_info=True)
            return

    def _normalise_archive_entry(self, raw: str) -> str | None:
        raw = raw.strip().replace("\\", "/").lstrip("./")
        raw = str(PurePosixPath(raw))
        markers = (
            "app/configuration/", "app/data/", "app/cache/avatars/", "app/voices/",
            "app/rvc_models/", "assets/ambient/", "assets/backgrounds/", "assets/emotions/",
            "assets/local_llm/", "assets/rvc_models/", "assets/live2d/", "assets/vrm/",
        )
        lower = raw.lower()
        for marker in markers:
            idx = lower.find(marker)
            if idx >= 0:
                candidate = raw[idx:]
                if candidate.lower().startswith("app/configuration/"):
                    if candidate.lower() not in {p.lower() for p in CONFIG_FILES}:
                        continue
                return candidate
        basename = PurePosixPath(raw).name.lower()
        if basename in {"settings.json", "api.json", "characters.json", "branding.json"}:
            return f"app/configuration/{basename}"
        return None

    def _validate_payload(self, configs: dict[str, bytes], rel_paths) -> None:
        if not configs:
            raise BackupError(
                "Im Backup wurden keine gültigen SoW-Konfigurationsdateien gefunden. Unterstützt werden ZIP-Backups mit app/configuration aus 2.5.1 und Backups aus 2.5.3."
            )
        for rel, data in configs.items():
            try:
                parsed = json.loads(data.decode("utf-8-sig"))
            except Exception as exc:
                raise BackupError(f"Ungültige JSON-Datei im Backup ({rel}): {exc}") from exc
            if not isinstance(parsed, dict):
                raise BackupError(f"Die Datei {rel} muss ein JSON-Objekt enthalten.")
        if not any(p in CONFIG_FILES for p in rel_paths):
            raise BackupError("Das Backup enthält keine unterstützte Soul-of-Waifu-Konfiguration.")

    def _migrate_settings(self, data: bytes) -> bytes:
        try:
            settings = json.loads(data.decode("utf-8-sig"))
        except Exception as exc:
            raise BackupError(f"Die Backup-Einstellungen sind ungültig: {exc}") from exc
        if not isinstance(settings, dict):
            raise BackupError("settings.json muss ein JSON-Objekt enthalten.")
        main = settings.get("main_settings")
        if not isinstance(main, dict):
            main = {}
            settings["main_settings"] = main
        from app.configuration.configuration import ConfigurationSettings
        for key, value in ConfigurationSettings._main_setting_defaults().items():
            if key not in main:
                main[key] = copy.deepcopy(value)
        try:
            context_size = int(main.get("context_size", 8192) or 8192)
        except (TypeError, ValueError):
            context_size = 8192
        if 0 < context_size < 8192:
            main["context_size"] = 8192
        try:
            old_schema = int(main.get("sow_schema_version", 0) or 0)
        except (TypeError, ValueError):
            old_schema = 0
        main["sow_schema_version"] = max(old_schema, 253)
        user_data = settings.get("user_data")
        if not isinstance(user_data, dict):
            user_data = {}
            settings["user_data"] = user_data
        user_defaults = {
            "default_persona": "None",
            "personas": {},
            "presets": {},
            "current_character_image": "None",
        }
        for key, value in user_defaults.items():
            user_data.setdefault(key, copy.deepcopy(value))
        return json.dumps(settings, ensure_ascii=False, indent=4).encode("utf-8")

    def _detect_version(self, configs: dict[str, bytes]) -> str:
        if self._detected_source_version:
            return self._detected_source_version
        return "2.5.1 oder älter (Legacy-Backup)" if "app/configuration/settings.json" in configs else "Legacy-Datenbackup"

    @staticmethod
    def _is_allowed(rel: str) -> bool:
        rel = rel.replace("\\", "/").lstrip("/")
        if rel in CONFIG_FILES:
            return True
        return rel.startswith(BASE_DIRS + OPTIONAL_DIRS)

    @staticmethod
    def _normalize_relative(rel: str) -> str | None:
        normalized = rel.replace("\\", "/").lstrip("./").lstrip("/")
        pp = PurePosixPath(normalized)
        if pp.is_absolute() or any(part in ("..", "") for part in pp.parts):
            return None
        return pp.as_posix()

    @staticmethod
    def _skip_file(path: Path) -> bool:
        return path.name in {".gitkeep", ".DS_Store", "Thumbs.db"} or "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}

    def _is_inside_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.root)
            return True
        except ValueError:
            return False
