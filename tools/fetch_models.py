r"""
Laedt die zwei kleinen Modelle, die Yume Companion beim Start im Programmordner erwartet, wenn du aus dem Quelltext installierst
(im Setup-Installer sind sie schon enthalten):

  app/utils/e5-small-en-ru                       Einbettungsmodell fuer Gedaechtnis und Lorebooks (d0rj/e5-small-en-ru, MIT)
  app/utils/emotions/detector                    Gefuehls-Erkennung, 28 Gefuehle (joeddav/distilbert-base-uncased-go-emotions-student, MIT)

Aufruf (im Projektordner, mit der Python-Umgebung der App):
    app\data\envs\sow\python.exe tools\fetch_models.py
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
JOBS = [
    ("d0rj/e5-small-en-ru", os.path.join(ROOT, "app", "utils", "e5-small-en-ru")),
    ("joeddav/distilbert-base-uncased-go-emotions-student", os.path.join(ROOT, "app", "utils", "emotions", "detector")),
]


def main(only_config=False):
    from huggingface_hub import snapshot_download, hf_hub_download
    for repo, target in JOBS:
        os.makedirs(target, exist_ok=True)
        if only_config:  # nur zum Testen der Namen
            print(repo, "->", hf_hub_download(repo, "config.json", local_dir=target))
            continue
        marker = os.path.join(target, "config.json")
        weights = [f for f in ("model.safetensors", "pytorch_model.bin") if os.path.exists(os.path.join(target, f))]
        if os.path.exists(marker) and weights:
            print("vorhanden:", target)
            continue
        print("lade", repo, "...")
        snapshot_download(repo, local_dir=target, allow_patterns=["*.json", "*.txt", "*.model", "*.safetensors", "1_Pooling/*"])
        print("fertig:", target)


if __name__ == "__main__":
    main(only_config="--test" in sys.argv)
