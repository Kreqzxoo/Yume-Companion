import os
import time
import shutil
import logging
import traceback
import zipfile
import datetime
from pathlib import Path
from typing import Optional, Callable

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("ProfileBackup")

SCHEMA_VERSION = 1
PACK_FORMAT = "yumepack"            # the format of new backups (file extension .yumepack)
PACK_EXT = ".yumepack"
LEGACY_FORMATS = ("sowpack",)       # backups of Soul of Waifu / older versions (.sowpack) can still be restored
PACK_EXTS = (PACK_EXT, ".sowpack")
SAFETY_ROTATION_KEEP = 5
PRE_RESTORE_PREFIX = "pre_restore_"
RESTORE_TMP_PREFIX = ".restore_tmp_"

STORED_EXTENSIONS = {
    ".gguf", ".wav", ".mp3", ".ogg", ".flac", ".webp", ".png", ".jpg",
    ".jpeg", ".gif", ".zip", ".7z", ".rar", ".mp4", ".webm", ".ico",
}

SKIP_DIR_NAMES = {"__pycache__", ".git"}
SKIP_FILE_SUFFIXES = (".pyc", ".pyo")


class BackupGroup:
    def __init__(self, key, title_key, paths, default_on=True,
                 locked=False, warning=None, always_in_safety=False):
        self.key = key
        self.title_key = title_key
        self.paths = paths
        self.default_on = default_on
        self.locked = locked
        self.warning = warning
        self.always_in_safety = always_in_safety


BACKUP_GROUPS = [
    BackupGroup(
        key="characters",
        title_key="backup_grp_characters",
        paths=[
            "app/configuration/characters.json",
            "app/configuration/characters",
        ],
        default_on=True,
        locked=True,
        always_in_safety=True,
    ),
    BackupGroup(
        key="user_data",
        title_key="backup_grp_user_data",
        paths=["app/configuration/settings.json"],
        default_on=True,
        always_in_safety=True,
    ),
    BackupGroup(
        key="api_keys",
        title_key="backup_grp_api_keys",
        paths=["app/configuration/api.json"],
        default_on=False,
        warning="api",
        always_in_safety=True,
    ),
    BackupGroup(
        key="soul_memory",
        title_key="backup_grp_soul_memory",
        paths=[".soul", "app/data/.soul"],
        default_on=True,
        always_in_safety=True,
    ),
    BackupGroup(
        key="soul_stage",
        title_key="backup_grp_soul_stage",
        paths=[
            ".soul_stage/scenes.json",
            ".soul_stage/npc_memory",
        ],
        default_on=True,
        always_in_safety=True,
    ),
    BackupGroup(
        key="avatars_cache",
        title_key="backup_grp_avatars",
        paths=["app/cache"],
        default_on=True,
        always_in_safety=True,
    ),
    BackupGroup(
        key="media_assets",
        title_key="backup_grp_media",
        paths=["assets/backgrounds", "assets/ambient"],
        default_on=True,
        always_in_safety=True,
    ),
    BackupGroup(
        key="live2d_assets",
        title_key="backup_grp_live2d",
        paths=["assets/emotions"],
        default_on=True,
        warning="size",
    ),
    BackupGroup(
        key="tts_voices",
        title_key="backup_grp_voices",
        paths=["app/voices"],
        default_on=False,
    ),
    BackupGroup(
        key="rvc_models",
        title_key="backup_grp_rvc",
        paths=["assets/rvc_models"],
        default_on=False,
        warning="size",
    ),
    BackupGroup(
        key="local_models",
        title_key="backup_grp_models",
        paths=["assets/local_llm"],
        default_on=False,
        warning="size",
    ),
]

GROUPS_BY_KEY = {g.key: g for g in BACKUP_GROUPS}

SAFETY_GROUP_KEYS = [g.key for g in BACKUP_GROUPS if g.always_in_safety]

def _is_skippable(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.endswith(SKIP_FILE_SUFFIXES)

def iter_group_files(group: BackupGroup, root: str):
    root_abs = os.path.abspath(root)
    seen = set()
    for rel in group.paths:
        abs_path = os.path.join(root_abs, *rel.replace("\\", "/").split("/"))
        if not os.path.exists(abs_path):
            continue
        if os.path.isfile(abs_path):
            if abs_path in seen:
                continue
            seen.add(abs_path)
            yield abs_path, rel.replace("\\", "/")
        else:
            for dirpath, dirnames, filenames in os.walk(abs_path):
                dirnames[:] = [d for d in dirnames if not _is_skippable(d)]
                for fname in filenames:
                    if _is_skippable(fname):
                        continue
                    fpath = os.path.join(dirpath, fname)
                    if fpath in seen:
                        continue
                    seen.add(fpath)
                    arc = os.path.relpath(fpath, root_abs).replace("\\", "/")
                    yield fpath, arc


def estimate_group(group: BackupGroup, root: str):
    total = 0
    count = 0
    for fpath, _arc in iter_group_files(group, root):
        try:
            total += os.path.getsize(fpath)
            count += 1
        except OSError:
            pass
    return total, count


def format_size(num_bytes) -> str:
    value = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _choose_zip_method(file_name: str) -> int:
    ext = os.path.splitext(file_name)[1].lower()
    return zipfile.ZIP_STORED if ext in STORED_EXTENSIONS else zipfile.ZIP_DEFLATED

def build_manifest(root: str, selected_keys, app_version: str = "") -> dict:
    contents = {}
    counts = {}
    for g in BACKUP_GROUPS:
        if g.key not in selected_keys:
            continue
        total, count = estimate_group(g, root)
        contents[g.key] = True
        counts[g.key] = count
    return {
        "schema_version": SCHEMA_VERSION,
        "app_version": app_version,
        "format": PACK_FORMAT,
        "created_at": datetime.datetime.now().isoformat(),
        "contents": contents,
        "counts": counts,
    }

def read_manifest(pack_path: str):
    try:
        with zipfile.ZipFile(pack_path, "r") as zf:
            names = set(zf.namelist())
            if "manifest.json" not in names:
                return None, "no_manifest"
            data = zf.read("manifest.json")
            import json
            manifest = json.loads(data.decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format") not in (PACK_FORMAT,) + LEGACY_FORMATS:
                return None, "bad_manifest"
            if int(manifest.get("schema_version", 0)) > SCHEMA_VERSION:
                return manifest, "newer_version"
            return manifest, None
    except zipfile.BadZipFile:
        return None, "bad_zip"
    except Exception as e:
        logger.warning(f"[ProfileBackup] read_manifest failed: {e}")
        return None, "unreadable"

class ExportWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, dest_path: str, root: str, selected_keys, app_version: str = "", parent=None):
        super().__init__(parent)
        self.dest_path = dest_path
        self.root = root
        self.selected_keys = list(selected_keys)
        self.app_version = app_version
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            groups = [GROUPS_BY_KEY[k] for k in self.selected_keys if k in GROUPS_BY_KEY]
            if "soul_memory" in self.selected_keys:
                try:
                    from app.utils import organizer
                    organizer.export_to(self.root)          # appointments, reminders, lists, memory, routines go along with the memory group
                except Exception:
                    logger.debug("organizer data could not be added to the backup", exc_info=True)

            plan = []
            for g in groups:
                for fpath, arc in iter_group_files(g, self.root):
                    if os.path.abspath(fpath) == os.path.abspath(self.dest_path):
                        continue
                    plan.append((fpath, arc))

            if not plan:
                self.failed.emit("nothing_to_export")
                return

            manifest = build_manifest(self.root, self.selected_keys, self.app_version)
            os.makedirs(os.path.dirname(os.path.abspath(self.dest_path)) or ".", exist_ok=True)

            total = len(plan)
            done = 0
            last_emit = time.monotonic()

            with zipfile.ZipFile(self.dest_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                info = zipfile.ZipInfo("manifest.json", date_time=time.localtime(time.time())[:6])
                zf.writestr(info, __import__("json").dumps(manifest, ensure_ascii=False, indent=2))

                for fpath, arc in plan:
                    if self._cancel:
                        try:
                            zf.close()
                        except Exception:
                            pass
                        try:
                            os.remove(self.dest_path)
                        except OSError:
                            pass
                        self.cancelled.emit()
                        return

                    arc_full = f"files/{arc}"
                    try:
                        method = _choose_zip_method(fpath)
                        info = zipfile.ZipInfo(arc_full, date_time=time.localtime(time.time())[:6])
                        info.compress_type = method
                        info.external_attr = 0o600 << 16
                        with open(fpath, "rb") as fh:
                            zf.writestr(info, fh.read(), compress_type=method)
                    except OSError as e:
                        logger.warning(f"[ProfileBackup] Skipped '{fpath}': {e}")

                    done += 1
                    now = time.monotonic()
                    if now - last_emit >= 0.15 or done == total:
                        last_emit = now
                        pct = 5 + int(done / max(1, total) * 90)
                        name = os.path.basename(fpath)
                        if len(name) > 46:
                            name = name[:43] + "..."
                        self.progress.emit(pct, f"{done}/{total}  ·  {name}")

            self.progress.emit(100, "OK")
            self.finished_ok.emit(self.dest_path)

        except PermissionError as e:
            logger.error(f"[ProfileBackup] Export permission error: {e}")
            self.failed.emit("permission")
        except Exception as e:
            logger.error(f"[ProfileBackup] Export failed: {e}\n{traceback.format_exc()}")
            self.failed.emit(str(e))

def _backup_dir(root: str) -> Path:
    return Path(root) / ".soul_stage" / "backups"


def create_safety_snapshot(root: str, tag: str = PRE_RESTORE_PREFIX,
                           group_keys=None, progress_cb: Optional[Callable[[int, str], None]] = None):
    keys = group_keys or SAFETY_GROUP_KEYS
    groups = [GROUPS_BY_KEY[k] for k in keys if k in GROUPS_BY_KEY]

    bdir = _backup_dir(root)
    bdir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = bdir / f"{tag}{stamp}.zip"

    plan = []
    for g in groups:
        for fpath, arc in iter_group_files(g, root):
            plan.append((fpath, arc))

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        meta = {
            "type": "pre_restore_snapshot",
            "tag": tag,
            "created_at": datetime.datetime.now().isoformat(),
            "files": len(plan),
        }
        info = zipfile.ZipInfo("_snapshot_meta.json", date_time=time.localtime(time.time())[:6])
        zf.writestr(info, __import__("json").dumps(meta))

        for i, (fpath, arc) in enumerate(plan):
            if progress_cb and i % 20 == 0:
                progress_cb(int(i / max(1, len(plan)) * 100), os.path.basename(fpath))
            method = _choose_zip_method(fpath)
            info = zipfile.ZipInfo(arc, date_time=time.localtime(time.time())[:6])
            info.compress_type = method
            with open(fpath, "rb") as fh:
                zf.writestr(info, fh.read(), compress_type=method)

    _rotate_snapshots(bdir, tag, SAFETY_ROTATION_KEEP)
    logger.info(f"[ProfileBackup] Safety snapshot created: {out_path}")
    return str(out_path)


def _rotate_snapshots(bdir: Path, prefix: str, keep: int):
    try:
        snaps = sorted(
            [p for p in bdir.glob(f"{prefix}*.zip")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in snaps[keep:]:
            try:
                old.unlink()
            except OSError:
                pass
    except Exception as e:
        logger.warning(f"[ProfileBackup] Snapshot rotation failed: {e}")


def list_safety_snapshots(root: str, tag: str = PRE_RESTORE_PREFIX):
    bdir = _backup_dir(root)
    if not bdir.exists():
        return []
    return sorted(
        [str(p) for p in bdir.glob(f"{tag}*.zip")],
        key=lambda p: os.path.getmtime(p),
        reverse=True,
    )


def rollback_from_snapshot(root: str, snapshot_path: str) -> bool:
    try:
        with zipfile.ZipFile(snapshot_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith("/") or name.startswith("_"):
                    continue
                target = os.path.join(root, *name.split("/"))
                os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
        logger.warning(f"[ProfileBackup] Rollback from {snapshot_path} completed.")
        return True
    except Exception as e:
        logger.error(f"[ProfileBackup] Rollback FAILED: {e}", exc_info=True)
        return False

class RestoreWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, pack_path: str, root: str, parent=None):
        super().__init__(parent)
        self.pack_path = pack_path
        self.root = root
        self._cancel = False
        self._applying = False

    def cancel(self):
        if not self._applying:
            self._cancel = True

    def _extract_all(self, tmp_dir: str) -> int:
        with zipfile.ZipFile(self.pack_path, "r") as zf:
            entries = [n for n in zf.namelist() if not n.endswith("/")]
            total = len(entries)
            for i, name in enumerate(entries):
                if self._cancel:
                    raise asyncio_cancel()
                target = os.path.join(tmp_dir, *name.split("/"))
                os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
                with zf.open(name) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                if i % 25 == 0 or i == total - 1:
                    self.progress.emit(10 + int(i / max(1, total) * 45),
                                       f"{i + 1}/{total}")
            return total

    def _apply_files(self, tmp_dir: str) -> int:
        files_root = os.path.join(tmp_dir, "files")
        applied = 0
        plan = []
        for dirpath, dirnames, filenames in os.walk(files_root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fname in filenames:
                plan.append(os.path.join(dirpath, fname))

        total = len(plan)
        for i, src in enumerate(plan):
            rel = os.path.relpath(src, files_root)
            target = os.path.join(self.root, *Path(rel).parts)
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            os.replace(src, target)
            applied += 1
            if i % 25 == 0 or i == total - 1:
                self.progress.emit(60 + int(i / max(1, total) * 38),
                                   f"{i + 1}/{total}")
        return applied

    def run(self):
        tmp_dir = None
        safety_path = None
        try:
            self.progress.emit(3, "validate")
            manifest, err = read_manifest(self.pack_path)
            if err == "newer_version":
                logger.warning("[ProfileBackup] Restoring a package from a newer app version.")
            elif err is not None or manifest is None:
                self.failed.emit(err or "bad_package")
                return

            if self._cancel:
                self.cancelled.emit()
                return

            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            tmp_dir = os.path.join(self.root, f"{RESTORE_TMP_PREFIX}{stamp}_{os.getpid()}")
            os.makedirs(tmp_dir, exist_ok=True)
            self.progress.emit(10, "extract")
            extracted = self._extract_all(tmp_dir)

            if self._cancel:
                self.cancelled.emit()
                return

            self.progress.emit(58, "safety_backup")
            safety_path = create_safety_snapshot(
                self.root, tag=PRE_RESTORE_PREFIX,
                progress_cb=lambda p, t: self.progress.emit(58 + int(p / 100 * 2), f"safety: {t}"),
            )

            if self._cancel:
                self.cancelled.emit()
                return

            self._applying = True
            self.progress.emit(60, "apply")
            try:
                applied = self._apply_files(tmp_dir)
            except Exception:
                logger.error("[ProfileBackup] Apply failed mid-way; rolling back.", exc_info=True)
                rolled = rollback_from_snapshot(self.root, safety_path) if safety_path else False
                self.failed.emit("apply_failed_rolled_back" if rolled else "apply_failed_no_rollback")
                return

            self.progress.emit(99, "cleanup")
            try:
                from app.utils import organizer
                organizer.import_from(self.root)
            except Exception:
                logger.debug("organizer data could not be restored", exc_info=True)

            self.finished_ok.emit({
                "applied": applied,
                "safety": safety_path,
                "manifest": manifest,
                "restart_recommended": True,
            })

        except _CancelledError:
            self.cancelled.emit()
        except zipfile.BadZipFile:
            self.failed.emit("bad_zip")
        except PermissionError:
            self.failed.emit("permission")
        except Exception as e:
            logger.error(f"[ProfileBackup] Restore failed: {e}\n{traceback.format_exc()}")
            if safety_path:
                rolled = rollback_from_snapshot(self.root, safety_path)
                self.failed.emit(f"failed_rolled_back:{e}" if rolled else f"failed:{e}")
            else:
                self.failed.emit(str(e))
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)


class _CancelledError(Exception):
    pass


def asyncio_cancel():
    raise _CancelledError()
