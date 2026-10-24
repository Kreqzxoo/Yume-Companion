import os
import json
import random
import base64
import asyncio
import logging
import datetime
import urllib.parse
from typing import Optional

import threading

import aiohttp

from app.configuration import configuration

logger = logging.getLogger("ImageGenerator")

_TIMEOUT_LOCAL = aiohttp.ClientTimeout(total=900, sock_connect=10)      # a large model (SDXL / Flux) may load for minutes first
_TIMEOUT_CLOUD = aiohttp.ClientTimeout(total=60)

PROVIDER_A1111    = "Automatic1111"
PROVIDER_COMFYUI  = "ComfyUI"
PROVIDER_DALLE    = "DALL-E 3"
PROVIDER_NOVELAI  = "NovelAI"
PROVIDER_FLUX     = "FLUX"

_COMFYUI_SAMPLER_TYPES = {
    "KSampler", "KSamplerAdvanced", "SamplerCustom", "SamplerCustomAdvanced",
}
_COMFYUI_LATENT_TYPES = {
    "EmptyLatentImage", "EmptySD3LatentImage", "EmptyFluxLatentImage",
}
_COMFYUI_NEGATIVE_MARKERS = ("negative", "neg", "нег")


def _clean_base_url(raw_url: Optional[str], default_port: int = 8188) -> str:
    if not raw_url or not str(raw_url).strip():
        return f"http://127.0.0.1:{default_port}"

    url = str(raw_url).strip()
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    if "#" in url:
        url = url.split("#")[0]

    parsed = urllib.parse.urlsplit(url)
    clean_path = parsed.path.rstrip('/')

    for suffix in ("/sdapi/v1/txt2img", "/sdapi/v1", "/prompt", "/object_info", "/view", "/history"):
        if clean_path.endswith(suffix):
            clean_path = clean_path[:-len(suffix)].rstrip('/')

    base = f"{parsed.scheme}://{parsed.netloc}{clean_path}".rstrip('/')
    return base if base else f"http://127.0.0.1:{default_port}"


_ACTIVE: dict = {}                     # running generation task -> its event loop
_CANCELLED: set = set()


def cancel_all():
    """Stop every running image generation (Stop button): cancel the tasks and tell the server to interrupt."""
    for task, loop in list(_ACTIVE.items()):
        _CANCELLED.add(task)
        try:
            loop.call_soon_threadsafe(task.cancel)
        except RuntimeError:
            pass
    if _ACTIVE:
        threading.Thread(target=_interrupt_server, daemon=True).start()


def _interrupt_server():
    import requests
    try:
        cfg = configuration.ConfigurationSettings()
        provider = cfg.get_main_setting("image_provider") or PROVIDER_A1111
        if provider in (PROVIDER_DALLE, PROVIDER_NOVELAI, PROVIDER_FLUX):
            return
        if "ComfyUI" in provider:
            requests.post(_clean_base_url(cfg.get_main_setting("image_api_url"), 8188) + "/interrupt", timeout=3)
        else:
            requests.post(_clean_base_url(cfg.get_main_setting("image_api_url"), 7860) + "/sdapi/v1/interrupt", timeout=3)
    except Exception:
        logger.debug("could not interrupt the image server", exc_info=True)


class ImageGenerator:
    """
    Manages async image generation across multiple providers:
    - Automatic1111 / SD WebUI / Forge (/sdapi/v1/txt2img)
    - ComfyUI Native API (/prompt, /history, /view)
    - Cloud APIs: DALL-E 3, NovelAI, FLUX (fal.ai)
    """

    def __init__(self) -> None:
        self.config = configuration.ConfigurationSettings()
        self.api_config = configuration.ConfigurationAPI()
        self.last_error = ""                  # short human-readable reason of the last failure (shown to the user)

    def _fail(self, message: str) -> None:
        self.last_error = message
        logger.error("Image generation failed: %s", message)

    async def generate_image(self, core_prompt: str, character_name: str) -> Optional[str]:
        """Registers the running task so the Stop button can cancel it, then runs the generation."""
        task = asyncio.current_task()
        _ACTIVE[task] = asyncio.get_running_loop()
        try:
            return await self._generate_image_impl(core_prompt, character_name)
        except asyncio.CancelledError:
            if task in _CANCELLED:
                logger.info("Image generation cancelled by the user.")
                return None
            raise
        finally:
            _ACTIVE.pop(task, None)
            _CANCELLED.discard(task)

    async def _generate_image_impl(self, core_prompt: str, character_name: str) -> Optional[str]:
        """
        Build the full prompt from settings, dispatch to the active provider,
        save the result, and return the gallery-relative path.
        """
        provider = self.config.get_main_setting("image_provider") or PROVIDER_A1111
        prefix   = self.config.get_main_setting("image_prefix_prompt") or (
            "masterpiece, best quality, very aesthetic, vivid colors, depth of field"
        )
        negative = self.config.get_main_setting("image_negative_prompt") or (
            "worst quality, low quality, normal quality, lowres, jpeg artifacts, blurry, "
            "bad anatomy, bad hands, missing fingers, extra digits, poorly drawn face, "
            "mutated, deformed, watermark, signature, text"
        )

        def _int_setting(key, default):
            try:
                return int(self.config.get_main_setting(key) or default)
            except (TypeError, ValueError):
                return default
        width  = _int_setting("image_width", 512)
        height = _int_setting("image_height", 768)
        steps  = _int_setting("image_steps", 20)
        self.last_error = ""

        full_prompt = f"{prefix}, {core_prompt}" if prefix else core_prompt

        logger.info("Generating image via [%s] | prompt: %s", provider, full_prompt)

        img_data: Optional[bytes] = None

        try:
            if provider == PROVIDER_A1111 or "Automatic1111" in provider:
                img_data = await self.generate_a1111(full_prompt, negative, width, height, steps)

            elif provider == PROVIDER_COMFYUI or "ComfyUI" in provider:
                img_data = await self.generate_comfyui(full_prompt, negative, width, height, steps)

            elif provider == PROVIDER_DALLE:
                img_data = await self.generate_dalle(full_prompt)

            elif provider == PROVIDER_NOVELAI:
                img_data = await self.generate_novelai(full_prompt, negative, width, height, steps)

            elif provider == PROVIDER_FLUX:
                img_data = await self.generate_flux(full_prompt, width, height)

            else:
                logger.error("Unsupported image provider: %s", provider)
                return None

            if img_data:
                logger.info("Successfully received image from %s (%d bytes). Saving...", provider, len(img_data))
                return await self.save_image(img_data, character_name)
            else:
                logger.warning("No image data returned from %s.", provider)
                if not self.last_error:
                    self.last_error = f"{provider} hat kein Bild geliefert (Details im Log)."
                return None

        except Exception as e:
            logger.error("Exception during image generation: %s", e, exc_info=True)
            self.last_error = f"{type(e).__name__}: {e}"[:160]
            return None

    # =========================================================================
    # Provider: ComfyUI
    # =========================================================================
    def _is_comfyui_ui_format(self, data) -> bool:
        return isinstance(data, dict) and ("nodes" in data or "links" in data)

    def _is_comfyui_api_format(self, data) -> bool:
        if not isinstance(data, dict) or not data:
            return False
        return all(isinstance(v, dict) and ("class_type" in v or "inputs" in v)
                for v in data.values())

    async def generate_comfyui(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
    ) -> Optional[bytes]:
        raw_url = self.config.get_main_setting("image_api_url")
        api_url = _clean_base_url(raw_url, default_port=8188)

        workflow = await self._load_comfyui_workflow(
            api_url, prompt, negative_prompt, width, height, steps
        )
        if workflow is None:
            return None

        logger.debug("ComfyUI: sending workflow: %s", json.dumps(workflow)[:1500])

        client_id = f"sow_{random.randint(1000, 9999)}"
        payload = {"prompt": workflow, "client_id": client_id}

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT_LOCAL) as session:
                prompt_url = f"{api_url}/prompt"

                async with session.post(prompt_url, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        self._fail(f"ComfyUI hat den Auftrag abgelehnt ({resp.status}): {body[:140]}")
                        return None
                    prompt_id = (await resp.json()).get("prompt_id")

                if not prompt_id:
                    logger.error("ComfyUI did not return a prompt_id.")
                    return None

                logger.info("ComfyUI: Queued prompt_id [%s], waiting for rendering...", prompt_id)

                history_url = f"{api_url}/history/{prompt_id}"
                for _ in range(900):                       # up to 15 minutes: the first run loads the model, Flux is slow
                    await asyncio.sleep(1.0)
                    async with session.get(history_url) as h_resp:
                        if h_resp.status != 200:
                            continue
                        h_data = await h_resp.json()
                        if prompt_id not in h_data:
                            continue

                        prompt_info = h_data[prompt_id]
                        status_info = prompt_info.get("status", {})
                        if status_info.get("status_str") == "error":
                            self._fail("ComfyUI meldet einen Fehler beim Rendern (z. B. Modell oder Workflow passt nicht) – Details im Log: "
                                       + str(status_info.get("messages"))[:100])
                            return None

                        for out_node in prompt_info.get("outputs", {}).values():
                            if out_node.get("images"):
                                img_info = out_node["images"][0]
                                view_params = urllib.parse.urlencode({
                                    "filename": img_info.get("filename"),
                                    "subfolder": img_info.get("subfolder", ""),
                                    "type": img_info.get("type", "output"),
                                })
                                async with session.get(f"{api_url}/view?{view_params}") as v_resp:
                                    if v_resp.status == 200:
                                        return await v_resp.read()
                                    logger.error("ComfyUI /view returned %d", v_resp.status)
                                    return None
        except aiohttp.ClientConnectionError:
            self._fail(f"Keine Verbindung zu ComfyUI ({api_url}) – läuft es?")
            return None
        except Exception as exc:
            logger.exception("ComfyUI error: %s", exc)
            self.last_error = f"{type(exc).__name__}: {exc}"[:160]
            return None

        self._fail("ComfyUI hat nach 15 Minuten kein Bild geliefert.")
        return None

    async def _load_comfyui_workflow(
        self, api_url: str, prompt: str, negative_prompt: str,
        width: int, height: int, steps: int,
    ) -> Optional[dict]:
        custom_raw = (self.config.get_main_setting("comfyui_custom_workflow_path")
                      or "").strip().strip('"').strip("'")

        if custom_raw:
            wf_path = self._resolve_workflow_path(custom_raw)
            if not wf_path:
                logger.error(
                    "ComfyUI: custom workflow file not found: %r "
                    "(setting 'comfyui_custom_workflow_path'). Aborting — "
                    "no silent fallback to the default workflow.",
                    custom_raw,
                )
                return None

            try:
                with open(wf_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except Exception as exc:
                logger.error("ComfyUI: cannot parse workflow %r: %s", wf_path, exc)
                return None

            if self._is_comfyui_ui_format(loaded):
                logger.error(
                    "ComfyUI: %r is saved in UI format (Ctrl+S). It must be exported "
                    "via 'Workflow -> Export (API)' in ComfyUI (enable Dev Mode if the "
                    "menu item is hidden). Aborting — no silent fallback.", wf_path)
                return None

            if not self._is_comfyui_api_format(loaded):
                logger.error("ComfyUI: %r is not an API-format workflow.", wf_path)
                return None

            self._patch_comfyui_workflow(loaded, prompt, negative_prompt,
                                         width, height, steps)
            logger.info("ComfyUI: custom workflow loaded: %s (%d nodes)",
                        wf_path, len(loaded))
            return loaded

        ckpt_name = await self._get_comfyui_checkpoint(api_url)
        if not ckpt_name:
            logger.error("ComfyUI: No checkpoints found in models/checkpoints folder!")
            return None

        logger.info("ComfyUI: no custom workflow configured, using default (ckpt: %s)",
                    ckpt_name)
        return self._build_default_comfyui_workflow(
            ckpt_name, prompt, negative_prompt, width, height, steps)

    @staticmethod
    def _resolve_workflow_path(raw_path: str) -> Optional[str]:
        path = raw_path.strip()
        if not path:
            return None
        if os.path.exists(path):
            return os.path.abspath(path)
        if not os.path.isabs(path):
            for base in (os.getcwd(),
                         os.path.join(os.getcwd(), "app"),
                         os.path.join(os.getcwd(), "app", "data")):
                candidate = os.path.join(base, path)
                if os.path.exists(candidate):
                    return candidate
        return None

    def _comfyui_override_params(self) -> bool:
        raw = (self.config.get_main_setting("comfyui_override_params")
               or "").strip().lower()
        if not raw:
            return True
        return raw not in ("0", "false", "no", "off")

    def _patch_comfyui_workflow(
        self, workflow: dict, prompt: str, negative_prompt: str,
        width: int, height: int, steps: int,
    ) -> None:
        positive_ids, negative_ids = set(), set()

        def _collect_clip(ref, acc, depth=0):
            if depth > 10 or not isinstance(ref, list) or len(ref) != 2:
                return
            nid = str(ref[0])
            node = workflow.get(nid)
            if not isinstance(node, dict):
                return
            if str(node.get("class_type", "")).startswith("CLIPTextEncode"):
                acc.add(nid)
                return
            for key, val in node.get("inputs", {}).items():
                if "conditioning" in str(key).lower():
                    _collect_clip(val, acc, depth + 1)

        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            if node.get("class_type") in _COMFYUI_SAMPLER_TYPES:
                inputs = node.get("inputs", {})
                if isinstance(inputs.get("positive"), list):
                    _collect_clip(inputs["positive"], positive_ids)
                if isinstance(inputs.get("negative"), list):
                    _collect_clip(inputs["negative"], negative_ids)

        unresolved = []
        for nid, node in workflow.items():
            if not isinstance(node, dict):
                continue
            if not str(node.get("class_type", "")).startswith("CLIPTextEncode"):
                continue
            inputs = node.get("inputs", {})
            if "text" not in inputs:
                continue
            if nid in negative_ids:
                inputs["text"] = negative_prompt
            elif nid in positive_ids:
                inputs["text"] = prompt
            else:
                unresolved.append((nid, node))

        for idx, (nid, node) in enumerate(unresolved):
            title = str(node.get("_meta", {}).get("title", "")).lower()
            is_neg = any(m in title for m in _COMFYUI_NEGATIVE_MARKERS) or (
                len(unresolved) == 2 and idx == 1 and not title)
            node["inputs"]["text"] = negative_prompt if is_neg else prompt

        if not positive_ids and not negative_ids and not unresolved:
            logger.warning("ComfyUI: no CLIPTextEncode* nodes found — prompt not injected.")

        override = self._comfyui_override_params()
        for node in workflow.values():
            if not isinstance(node, dict):
                continue
            ctype = str(node.get("class_type", ""))
            inputs = node.get("inputs", {})
            if not isinstance(inputs, dict):
                continue

            for seed_key in ("seed", "noise_seed"):
                if seed_key in inputs:
                    inputs[seed_key] = random.randint(1, 1125899906842624)

            if override and "steps" in inputs and ("Sampler" in ctype or "Scheduler" in ctype):
                inputs["steps"] = steps

            if override and ctype in _COMFYUI_LATENT_TYPES:
                if "width" in inputs:
                    inputs["width"] = width
                if "height" in inputs:
                    inputs["height"] = height

    @staticmethod
    def _build_default_comfyui_workflow(ckpt_name, prompt, negative_prompt,
                                        width, height, steps) -> dict:
        seed = random.randint(1, 1125899906842624)
        return {
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt_name}},
            "5": {"class_type": "EmptyLatentImage",
                  "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["4", 1], "text": prompt}},
            "7": {"class_type": "CLIPTextEncode",
                  "inputs": {"clip": ["4", 1], "text": negative_prompt}},
            "3": {"class_type": "KSampler", "inputs": {
                "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
                "latent_image": ["5", 0], "seed": seed, "steps": steps, "cfg": 7.0,
                "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1.0}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage",
                  "inputs": {"filename_prefix": "SoW_Generation", "images": ["8", 0]}},
        }

    async def _get_comfyui_checkpoint(self, api_url: str) -> Optional[str]:
        target_model = (self.config.get_main_setting("image_checkpoint") or "").strip().lower()

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                url = f"{api_url}/object_info/CheckpointLoaderSimple"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        ckpts = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]

                        if not ckpts or not isinstance(ckpts, list):
                            logger.error("ComfyUI returned an empty checkpoint list.")
                            return None

                        logger.info("ComfyUI available checkpoints: %s", ckpts)

                        if target_model:
                            for ckpt in ckpts:
                                if target_model in ckpt.lower():
                                    logger.info("Matched desired checkpoint: [%s] for keyword '%s'", ckpt, target_model)
                                    return ckpt
                            logger.warning("Specified checkpoint '%s' not found in ComfyUI. Falling back.", target_model)

                        for ckpt in ckpts:
                            name_lower = ckpt.lower()
                            if "inpaint" not in name_lower and "depth" not in name_lower:
                                logger.info("Auto-selected active checkpoint: [%s]", ckpt)
                                return ckpt

                        return ckpts[0]

        except Exception as e:
            logger.warning("Could not automatically list ComfyUI checkpoints: %s", e)

        return None

    # =========================================================================
    # Provider: Automatic1111 / SD-WebUI-Forge
    # =========================================================================
    async def generate_a1111(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
    ) -> Optional[bytes]:
        raw_url = self.config.get_main_setting("image_api_url")
        api_url = _clean_base_url(raw_url, default_port=7860)
        url = f"{api_url}/sdapi/v1/txt2img"

        payload = {
            "prompt":          prompt,
            "negative_prompt": negative_prompt,
            "width":           width,
            "height":          height,
            "steps":           steps,
            "sampler_name":    "Euler a",
            "sampler_index":   "Euler a",
            "cfg_scale":       7.0,
            "seed":            -1,
        }
        _ckpt = (self.config.get_main_setting("image_checkpoint") or "").strip()
        if _ckpt:
            payload["override_settings"] = {"sd_model_checkpoint": _ckpt}

        try:
            logger.debug("Connecting to A1111 / Forge at %s", url)
            async with aiohttp.ClientSession(timeout=_TIMEOUT_LOCAL) as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        images = data.get("images", [])
                        if images:
                            return base64.b64decode(images[0])
                    else:
                        body = await response.text()
                        self._fail(f"Der Bild-Server antwortete mit Fehler {response.status}: {body[:120]}")
                        return None

        except aiohttp.ClientConnectionError:
            self._fail(f"Keine Verbindung zu {api_url} – läuft die WebUI mit dem Startparameter --api?")
            return None
        except asyncio.TimeoutError:
            self._fail(f"Der Bild-Server hat nach {int(_TIMEOUT_LOCAL.total)} s nicht fertig geantwortet.")
            return None
        except Exception as exc:
            logger.exception("A1111: unexpected error: %s", exc)
            return None

    # =========================================================================
    # Provider: DALL-E 3
    # =========================================================================
    async def generate_dalle(self, prompt: str) -> Optional[bytes]:
        openai_key = self.api_config.get_token("OPEN_AI_API_TOKEN")
        if not openai_key:
            logger.error("DALL-E: no OpenAI API key configured.")
            return None

        gen_url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {openai_key}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model":           "dall-e-3",
            "prompt":          prompt,
            "n":               1,
            "size":            "1024x1024",
            "response_format": "b64_json"
        }

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT_CLOUD) as session:
                async with session.post(gen_url, headers=headers, json=payload) as gen_resp:
                    if gen_resp.status != 200:
                        body = await gen_resp.text()
                        logger.error("DALL-E generation error %d: %s", gen_resp.status, body[:300])
                        return None
                    gen_data = await gen_resp.json()
                    b64 = gen_data["data"][0]["b64_json"]
                    return base64.b64decode(b64)

        except Exception as exc:
            logger.exception("DALL-E error: %s", exc)
            return None

    # =========================================================================
    # Provider: NovelAI
    # =========================================================================
    async def generate_novelai(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
    ) -> Optional[bytes]:
        novelai_key = self.api_config.get_token("NOVELAI_API_TOKEN")
        if not novelai_key:
            logger.error("NovelAI: no API token configured.")
            return None

        url = "https://image.novelai.net/ai/generate-image"
        headers = {
            "Authorization": f"Bearer {novelai_key}",
            "Content-Type":  "application/json",
        }
        payload = {
            "input":  prompt,
            "model":  "nai-diffusion-4",
            "action": "generate",
            "parameters": {
                "width":           width,
                "height":          height,
                "steps":           steps,
                "scale":           7,
                "sampler":         "k_dpmpp_2m",
                "negative_prompt": negative_prompt,
                "n_samples":       1,
                "ucPreset":        0,
                "qualityToggle":   True,
            },
        }

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT_CLOUD) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        zip_bytes = await response.read()
                        return self._extract_novelai_image(zip_bytes)
                    else:
                        body = await response.text()
                        logger.error("NovelAI error %d: %s", response.status, body[:300])
                        return None

        except Exception as exc:
            logger.exception("NovelAI error: %s", exc)
            return None

    @staticmethod
    def _extract_novelai_image(zip_bytes: bytes) -> Optional[bytes]:
        import zipfile
        from io import BytesIO

        try:
            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".png"):
                        return zf.read(name)
            logger.error("NovelAI: no PNG found in zip response.")
            return None
        except zipfile.BadZipFile:
            logger.error("NovelAI: response is not a valid zip archive.")
            return None

    # =========================================================================
    # Provider: FLUX (fal.ai)
    # =========================================================================
    async def generate_flux(
        self,
        prompt: str,
        width: int,
        height: int,
    ) -> Optional[bytes]:
        fal_key = self.api_config.get_token("FAL_API_TOKEN")
        if not fal_key:
            logger.error("FLUX: no fal.ai API token configured.")
            return None

        url = "https://fal.run/fal-ai/flux-pro/v1.1"
        headers = {
            "Authorization": f"Key {fal_key}",
            "Content-Type":  "application/json",
        }
        payload = {
            "prompt":        prompt,
            "image_size":    {"width": width, "height": height},
            "num_images":    1,
            "output_format": "png",
        }

        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT_CLOUD) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        image_url = data["images"][0]["url"]
                        async with session.get(image_url) as img_resp:
                            if img_resp.status == 200:
                                return await img_resp.read()
                    else:
                        body = await response.text()
                        logger.error("FLUX error %d: %s", response.status, body[:300])
                        return None
        except Exception as exc:
            logger.exception("FLUX error: %s", exc)
            return None

    async def save_image(self, image_data: Optional[bytes], character_name: str) -> Optional[str]:
        if not image_data:
            return None

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"img_{timestamp}.png"

        base_dir = os.path.join(
            os.getcwd(),
            "app",
            "data",
            ".soul",
            character_name,
            "generated_images"
        )
        os.makedirs(base_dir, exist_ok=True)
        file_path = os.path.join(base_dir, filename)

        def _write():
            with open(file_path, "wb") as fh:
                fh.write(image_data)
            return f"generated_images/{filename}"

        return await asyncio.to_thread(_write)