"""Knowledge base: indexing (txt, md, docx, re-index only changed, deleted files vanish) and German full-text search. Temporary folders."""
import sys, os, tempfile, asyncio, time
sys.path.insert(0, '.')
from pathlib import Path
from app.utils import knowledge as kb
tmp = Path(tempfile.mkdtemp())
kb.DIR = tmp; kb.CONFIG = tmp / "knowledge.json"; kb.DB = tmp / "knowledge.db"
docs = tmp / "docs"; docs.mkdir()
(docs / "mietvertrag.txt").write_text("Mietvertrag\n\nDie Kündigungsfrist für den Mieter beträgt drei Monate zum Monatsende. Die Kaution beträgt zwei Nettokaltmieten.\n" * 3, encoding="utf-8")
(docs / "waschmaschine.md").write_text("# Waschmaschine\n\nDie Garantie läuft 24 Monate ab Kaufdatum. Bei Fehler E18 den Abpumpfilter reinigen.", encoding="utf-8")
import docx
d = docx.Document(); d.add_paragraph("Reiseplan Italien: Der Flug nach Rom geht am 14. Mai um 07:45 Uhr, Hotel Colosseo ist für fünf Nächte gebucht."); d.save(str(docs / "reise.docx"))
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
kb.save_folders([str(docs)])
check("folders saved", kb.folders() == [str(docs)])
r = kb.reindex()
s = kb.status()
check("3 files indexed", s["files"] == 3 and s["chunks"] >= 3)
hit = kb.search("Was steht im Mietvertrag zur Kündigung?")
check("finds the notice period by prefix (Kündigung -> Kündigungsfrist)", hit and "mietvertrag" in hit[0]["path"] and "drei Monate" in hit[0]["text"])
check("finds the error code", any("E18" in h["text"] for h in kb.search("Fehler E18 Waschmaschine")))
check("finds the docx", any("Rom" in h["text"] for h in kb.search("Wann geht mein Flug nach Rom?")))
check("nothing found for unrelated words", kb.search("Quantenchromodynamik Raumschiff") == [])
check("stop words only -> empty", kb.search("was ist das") == [])
# unchanged files are not read again; a changed one is; a deleted one disappears
before = kb.status()["chunks"]
kb.reindex()
check("second run keeps everything", kb.status()["chunks"] == before)
time.sleep(1.1)
(docs / "waschmaschine.md").write_text("# Waschmaschine\n\nDie Garantie läuft jetzt 36 Monate.", encoding="utf-8")
kb.reindex()
check("changed file re-read", any("36 Monate" in h["text"] for h in kb.search("Garantie Waschmaschine")) and not any("24 Monate" in h["text"] for h in kb.search("Garantie Waschmaschine")))
(docs / "reise.docx").unlink()
kb.reindex()
check("deleted file removed from the index", kb.search("Flug Rom") == [] and kb.status()["files"] == 2)
# the tool
from app.utils.ai_clients import tools as T
res = asyncio.run(T.KnowledgeTool().execute({"action": "search", "query": "Kaution Mietvertrag"}, {}))
check("tool search names file", res["success"] and "mietvertrag.txt" in res["result"] and "Kaution" in res["result"])
check("tool status", "Dateien" in asyncio.run(T.KnowledgeTool().execute({"action": "status"}, {}))["result"])
kb.save_folders([])
check("tool without folders explains setup", not asyncio.run(T.KnowledgeTool().execute({"action": "search", "query": "x"}, {}))["success"])
print("ALL OK" if ok else "FAILED")

# ---- meaning-based search (needs the embedding model: downloaded once, about 470 MB; the test is skipped without --semantic)
if "--semantic" in sys.argv:
    import numpy as np
    kb.save_folders([str(docs)])
    (docs / "kuendigung.txt").write_text("Wenn Sie den Vertrag beenden möchten, schicken Sie uns bitte spätestens drei Monate vor Laufzeitende ein Schreiben per Einschreiben.", encoding="utf-8")
    (docs / "rezept.txt").write_text("Für den Kuchen Eier, Zucker und Mehl verrühren und bei 180 Grad backen.", encoding="utf-8")
    kb.reindex()
    q = "Wie komme ich aus dem Abo raus?"
    check("keyword search alone finds nothing for this question", kb.search(q) == [] or "kuendigung" not in kb.search(q)[0]["path"])
    kb.set_semantic(True)
    check("semantic flag saved, folders kept", kb.semantic_enabled() and kb.folders() == [str(docs)])
    kb.reindex()
    check("vectors computed", kb.semantic_ready())
    hit = kb.search(q)
    check("meaning search finds the cancellation passage without shared words", hit and "kuendigung" in hit[0]["path"])
    check("unrelated question finds no cake recipe for taxes", not any("rezept" in h["path"] for h in kb.search("Wann muss ich die Steuererklärung abgeben?")))
    check("cake question finds the recipe", "rezept" in kb.search("Wie backe ich einen Kuchen?")[0]["path"])
    kb.set_semantic(False)
