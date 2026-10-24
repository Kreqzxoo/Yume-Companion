"""Regenerates the clean config templates (settings.json, api.json, characters.json) for the installer.

Run with any Python 3:  python make_templates.py "<working folder>"
Types stay exactly as in the working settings file (the app crashed with string defaults); personal values,
devices, tokens, models, tuned sampling values and themes are reset.
"""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
work = Path(sys.argv[1])
conf = work / "app" / "configuration"
dev = json.loads((conf / "settings.json").read_text(encoding="utf-8-sig"))
code_defaults = json.loads((HERE / "default_settings.json").read_text(encoding="utf-8"))["main_settings"]
main = copy.deepcopy(dev["main_settings"])


def coerce(value, like):
    try:
        if isinstance(like, bool):
            return bool(value) if not isinstance(value, str) else value.lower() in ("1", "true", "yes")
        if isinstance(like, int):
            return int(value)
        if isinstance(like, float):
            return float(value)
        if isinstance(like, str):
            return "" if value is None else str(value)
    except (TypeError, ValueError):
        return like
    return value


for key, val in code_defaults.items():
    if key in main:
        main[key] = coerce(val, main[key])

for key in ("app_custom_colors", "app_theme_name", "gui_theme", "chat_appearance", "ui_appearance", "window_theme",
            "vision_enabled", "vision_model_id", "vision_prompt", "web_auth_token", "dashboard_token", "android_host_id",
            "update_repo", "available_memory"):
    main.pop(key, None)

main.update({
    "active_llm_preset": None,
    "ambient": False, "ambient_sound": "", "ambient_volume": 50,
    "android_local_url": "", "android_remote_url": "", "android_wifi_ssid": "",
    "input_device": 0, "input_device_real_index": 0, "output_device": 0, "output_device_combo_index": 0,
    "output_device_real_index": 0,
    "program_language": 0, "translator": 0, "target_language": 0,
    "sow_system_status": False,
    "local_llm": "", "custom_args": "", "openai_model": "", "image_api_url": "", "image_checkpoint": "",
    "context_size": 8192, "gpu_layers": 0, "cpu_threads": 0, "cpu_moe_layers": 0, "llm_batch_size": 512,
    "temperature": 0.7, "top_p": 0.9, "min_p": 0.05, "frequency_penalty": 0.0, "presence_penalty": 0.0,
    "xtc_probability": 0.0, "xtc_threshold": 0.1, "dry_multiplier": 0.0, "dry_base": 1.75, "dry_allowed_length": 2,
    "tts_voicing_mode": 0, "tts_chunk_max_chars": 280, "tts_chunk_pause_ms": 140,
    "reasoning_mode": True, "reasoning_effort": "medium",
    "llm_cuda_gpu_indices": "0", "whisper_gpu_index": 0, "tts_gpu_index": 0, "qwen_gpu_index": 0,
    "aec_install_prompt_dismissed": False, "aec_install_prompt_version": 0,
    "chat_tools_enabled": True, "tool_preferences": {},
})

user = copy.deepcopy(dev["user_data"])
user.update({"default_persona": "None", "personas": {}, "lorebooks": {}, "author_notes": "",
             "current_character_image": "None", "custom_variable_presets": {}, "llm_presets": {}, "hub_tag_filter": ""})

out = {"main_settings": main, "user_data": user, "character_groups": {}}
(HERE / "settings.json").write_bytes((json.dumps(out, ensure_ascii=False, indent=4) + "\n").encode("utf-8"))

# German variant: only the program language differs
de = copy.deepcopy(out)
de["main_settings"]["program_language"] = 2
(HERE / "settings_de.json").write_bytes((json.dumps(de, ensure_ascii=False, indent=4) + "\n").encode("utf-8"))

api = json.loads((conf / "api.json").read_text(encoding="utf-8-sig"))
api = {k: ("" if isinstance(v, str) else v) for k, v in api.items()}
(HERE / "api.json").write_bytes((json.dumps(api, ensure_ascii=False, indent=4) + "\n").encode("utf-8"))
(HERE / "characters.json").write_bytes(b'{\n    "version": 2,\n    "character_list": {}\n}\n')
print("templates written:", HERE, "| main keys:", len(main))
