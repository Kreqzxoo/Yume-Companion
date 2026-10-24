import os
import re
import json
import shutil
import zipfile
import asyncio
import logging
import threading
from pathlib import Path

import aiohttp
from PyQt6 import QtCore

logger = logging.getLogger("LlamaUpdater")


class LlamaUpdater(QtCore.QObject):
    progress_signal = QtCore.pyqtSignal(int, str)
    finished_signal = QtCore.pyqtSignal(bool, str)
    fetch_done_signal = QtCore.pyqtSignal(object, str)

    def __init__(self, backend_dir: Path):
        super().__init__()
        self.backend_dir = backend_dir
        self.cache_dir = backend_dir / "_update_cache"
        self.backup_dir = backend_dir / "_backup"
        self.version_file = backend_dir / "version.json"
        self.github_api_url = "https://api.github.com/repos/ggml-org/llama.cpp/releases"

        self._worker_thread = None

    def start_fetch(self):
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        nightly, err = asyncio.run(self.fetch_latest_release())
        self.fetch_done_signal.emit(nightly, err or "")

    def start_rollback(self, backend_type: str):
        threading.Thread(
            target=self._rollback_worker, args=(backend_type,), daemon=True
        ).start()

    def _rollback_worker(self, backend_type: str):
        ok, msg = asyncio.run(self.restore_backup(backend_type))
        self.finished_signal.emit(ok, msg)

    def start_update(self, asset_urls: list, backend_type: str, version_tag: str):
        if not asset_urls:
            self.finished_signal.emit(False, "No assets to download.")
            return
        threading.Thread(
            target=self._update_worker,
            args=(asset_urls, backend_type, version_tag),
            daemon=True,
        ).start()

    async def fetch_latest_release(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.github_api_url,
                    params={"per_page": 15},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    if response.status != 200:
                        return None, f"GitHub API error: HTTP {response.status}"
                    data = await response.json()
                    nightly = next(
                        (r for r in data
                         if str(r.get("tag_name", "")).lower().startswith("b")),
                        None
                    )
                    if nightly is None:
                        return None, "No nightly build found in the latest GitHub releases."
                    return nightly, None
        except Exception as e:
            return None, str(e)

    def fetch_latest_release_blocking(self):
        return asyncio.run(self.fetch_latest_release())

    def _get_current_version(self, backend_type: str) -> str:
        if self.version_file.exists():
            try:
                data = json.loads(self.version_file.read_text(encoding="utf-8"))
                return data.get(backend_type.lower(), "unknown")
            except Exception:
                pass
        return "unknown"

    def _match_assets(self, assets: list, backend_type: str) -> list:
        backend_type = backend_type.lower()

        def matches(name, keywords):
            return all(kw in name for kw in keywords) and "arm64" not in name

        if backend_type == "cuda":
            for asset in assets:
                name = asset.get("name", "").lower()
                if "cudart" in name:
                    continue
                if matches(name, ["llama", "win", "cuda", "12.4", "x64"]):
                    return [asset["browser_download_url"]]
            return []

        matched_urls = []
        for asset in assets:
            name = asset.get("name", "").lower()
            if not name.endswith(".zip"):
                continue

            if backend_type == "cpu" and matches(name, ["llama", "win", "cpu", "x64"]):
                matched_urls.append(asset["browser_download_url"])

            elif backend_type == "vulkan" and matches(name, ["llama", "win", "vulkan", "x64"]):
                matched_urls.append(asset["browser_download_url"])

            elif backend_type == "hip" and (
                matches(name, ["llama", "win", "hip", "x64"])
                or matches(name, ["llama", "win", "rocm", "x64"])
            ):
                matched_urls.append(asset["browser_download_url"])

            elif backend_type == "sycl" and matches(name, ["llama", "win", "sycl", "x64"]):
                matched_urls.append(asset["browser_download_url"])

        if len(matched_urls) > 1:
            matched_urls = matched_urls[:1]

        return matched_urls

    def _update_worker(self, asset_urls: list, backend_type: str, version_tag: str):
        asyncio.run(self._download_and_install(asset_urls, backend_type, version_tag))

    async def _download_and_install(self, asset_urls: list, backend_type: str, version_tag: str):
        target_folder = self.backend_dir / backend_type.lower()
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        try:
            await asyncio.to_thread(self._create_backup, target_folder)
            await asyncio.to_thread(target_folder.mkdir, parents=True, exist_ok=True)

            total_parts = max(len(asset_urls), 1)

            timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=300)
            async with aiohttp.ClientSession(timeout=timeout) as session:

                for idx, url in enumerate(asset_urls):
                    zip_path = self.cache_dir / f"update_{idx}.zip"

                    async with session.get(url) as response:
                        if response.status != 200:
                            raise Exception(
                                f"Failed to download file from {url} "
                                f"(HTTP {response.status})"
                            )

                        total_size = int(response.headers.get("content-length", 0))
                        downloaded = 0
                        last_percent = -1
                        last_emit_s = 0.0

                        with open(zip_path, "wb") as f:
                            async for chunk in response.content.iter_chunked(1 << 20):
                                f.write(chunk)
                                downloaded += len(chunk)

                                if total_size > 0:
                                    part_fraction = downloaded / total_size
                                else:
                                    part_fraction = min(downloaded / (500 * 1024 * 1024), 1.0)

                                percent = int(((idx + part_fraction) / total_parts) * 100)
                                now_s = asyncio.get_running_loop().time()

                                if percent != last_percent and (now_s - last_emit_s) >= 0.12:
                                    self._emit_progress(
                                        percent, idx, total_parts,
                                        downloaded, total_size
                                    )
                                    last_percent = percent
                                    last_emit_s = now_s

                    final_percent = int(((idx + 1) / total_parts) * 100)
                    if final_percent != last_percent:
                        self._emit_progress(
                            final_percent, idx, total_parts,
                            downloaded, total_size
                        )

                    self.progress_signal.emit(
                        100, f"Extracting part [{idx + 1}/{len(asset_urls)}]..."
                    )

                    await asyncio.to_thread(self._extract_zip, zip_path, target_folder)

                    if zip_path.exists():
                        os.remove(zip_path)

            await asyncio.to_thread(self._write_version, backend_type, version_tag)

            self.finished_signal.emit(
                True,
                f"Successfully updated {backend_type.upper()} engine to {version_tag}!"
            )

        except PermissionError:
            self.finished_signal.emit(
                False, "Permission Denied! Ensure the LLM server is STOPPED."
            )
            await self.restore_backup(backend_type)
        except Exception as e:
            logger.exception("Update failed")
            self.finished_signal.emit(False, f"Update error: {e}")
            await self.restore_backup(backend_type)
        finally:
            try:
                if self.cache_dir.exists():
                    for p in self.cache_dir.iterdir():
                        if p.is_file():
                            p.unlink()
            except Exception:
                pass

    def _emit_progress(self, percent, idx, total_parts, downloaded, total_size):
        mb_done = downloaded // (1024 * 1024)
        text = f"Downloading part [{idx + 1}/{total_parts}]... {mb_done}MB"
        if total_size:
            text += f" / {total_size // (1024 * 1024)}MB"
        self.progress_signal.emit(percent, text)

    def _extract_zip(self, zip_path: Path, target_folder: Path):
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith((".exe", ".dll")):
                    filename = Path(file_info.filename).name
                    extracted_path = target_folder / filename
                    if extracted_path.exists():
                        os.remove(extracted_path)
                    with zip_ref.open(file_info) as source, \
                            open(extracted_path, "wb") as target:
                        shutil.copyfileobj(source, target)

    def _write_version(self, backend_type: str, version_tag: str):
        ver_data = {}
        if self.version_file.exists():
            try:
                ver_data = json.loads(self.version_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        ver_data[backend_type.lower()] = version_tag
        self.version_file.write_text(
            json.dumps(ver_data, indent=4), encoding="utf-8"
        )

    def _create_backup(self, target_folder: Path):
        if not target_folder.exists():
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_folder = self.backup_dir / target_folder.name
        if backup_folder.exists():
            shutil.rmtree(backup_folder)
        shutil.copytree(target_folder, backup_folder)
        logger.info(f"Backup created for {target_folder.name}")

    async def restore_backup(self, backend_type: str):
        target_folder = self.backend_dir / backend_type.lower()
        backup_folder = self.backup_dir / backend_type.lower()

        if not backup_folder.exists():
            return False, "No backup found for this backend."

        try:
            await asyncio.to_thread(
                self._restore_backup_blocking, target_folder, backup_folder
            )
            logger.info(f"Reverted {backend_type} to previous version")
            return True, "Successfully reverted to the previous version!"
        except Exception as e:
            logger.error(f"Failed to restore backup: {e}")
            return False, f"Failed to restore backup: {e}"

    def _restore_backup_blocking(self, target_folder: Path, backup_folder: Path):
        if target_folder.exists():
            shutil.rmtree(target_folder)
        shutil.copytree(backup_folder, target_folder)