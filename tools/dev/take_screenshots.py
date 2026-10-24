"""
Macht die Screenshots fuer die Dokumentation (docs/images/pc) direkt aus der laufenden App.

Aufruf (im Projektordner, mit der Python-Umgebung von Yume Companion):

    set YUME_ROOT=C:\\Pfad\\zu\\Yume-Companion
    app\\data\\envs\\sow\\python.exe tools\\dev\\take_screenshots.py [Zielordner] [seiten|optionen|dialoge|chat|alle]

Voraussetzung: tools/demo/make_demo_content.py wurde einmal ausgefuehrt (Demo-Charaktere ohne private Daten).
Das Skript startet die echte Oberflaeche, schaltet Seiten um und speichert Bilder des Fensters.
Pfade mit Benutzernamen und Felder, die Token, Schluessel, Adressen oder Passwoerter enthalten koennten,
werden vor dem Foto ersetzt bzw. verdeckt.
"""
import asyncio
import os
import re
import sys

ROOT = os.environ.get("YUME_ROOT") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "images", "pc")
WHAT = sys.argv[2] if len(sys.argv) > 2 else "alle"
os.makedirs(OUT, exist_ok=True)
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ["PATH"] = os.path.join(ROOT, "app", "ffmpeg", "bin") + os.pathsep + os.environ.get("PATH", "")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read().split('if __name__ == "__main__":')[0]
g = {"__name__": "yumeshots", "__file__": os.path.join(ROOT, "main.py")}
exec(compile(src, "main.py", "exec"), g)

from PyQt6 import QtCore, QtWidgets  # noqa: E402
from qasync import QEventLoop  # noqa: E402

app = QtWidgets.QApplication(sys.argv[:1])
loop = QEventLoop(app)
asyncio.set_event_loop(loop)
win = g["MainWindow"]()
win.resize(1600, 900)
win.show()
ui = win.ui
sig = win.interface_signals

HIDE = ("token", "key", "password", "secret", "ssid", "url", "host", "address", "mail_user", "iban", "bic")
PATH_RE = re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+\\(?:OneDrive\\)?(?:Desktop\\)?(?:[^\\\s]*Projekt\\)?(?:[^\\]*(?:BETA|Yume[^\\]*)\\)?", re.I)
NAME_RE = re.compile(re.escape(os.environ.get("USERNAME", "benutzer")), re.I)  # Windows-Benutzername; der Autorenname aus branding.json bleibt sichtbar


ROOT_WIN = ROOT.replace("/", "\\")


def clean(text):
    new = text.replace(ROOT_WIN, "C:\\Yume-Companion").replace(ROOT, "C:/Yume-Companion")
    new = PATH_RE.sub(r"C:\\Yume-Companion\\", new)
    return NAME_RE.sub("Name", new)


def scrub():
    for le in win.findChildren(QtWidgets.QLineEdit):
        n = le.objectName().lower()
        if le.text() and (le.echoMode() != QtWidgets.QLineEdit.EchoMode.Normal or any(s in n for s in HIDE)):
            le.setText("••••••••")
        elif le.text() and clean(le.text()) != le.text():
            le.setText(clean(le.text()))
    for cls in (QtWidgets.QLabel, QtWidgets.QAbstractButton):
        for w in win.findChildren(cls):
            t = w.text()
            if t and clean(t) != t:
                w.setText(clean(t))
    for cls in (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit):
        for w in win.findChildren(cls):
            if cls is QtWidgets.QTextEdit and w.toPlainText() and clean(w.toPlainText()) != w.toPlainText():
                w.setPlainText(clean(w.toPlainText()))
            elif cls is QtWidgets.QPlainTextEdit and w.toPlainText() and clean(w.toPlainText()) != w.toPlainText():
                w.setPlainText(clean(w.toPlainText()))


async def wait(ms=900):
    await asyncio.sleep(ms / 1000)


async def snap(name, widget=None):
    await wait()
    scrub()
    await wait(200)
    (widget or win).grab().save(os.path.join(OUT, name + ".png"))
    print("saved", name, flush=True)


async def snap_tall(name, tab):
    """Ganze Seite: Fenster so hoch machen, dass der Inhalt der Scroll-Flaeche passt."""
    best = 0
    for sa in tab.findChildren(QtWidgets.QScrollArea):
        w = sa.widget()
        if w is not None:
            best = max(best, w.sizeHint().height(), w.height())
    if best <= 800:
        return
    h = min(best + 160, 9500)
    win.resize(1600, h)
    await wait(1400)
    scrub()
    win.grab().save(os.path.join(OUT, name + "_voll.png"))
    print("saved", name + "_voll", flush=True)
    win.resize(1600, 900)
    await wait(600)


def dialog_scrub(w):
    for cls in (QtWidgets.QLabel, QtWidgets.QAbstractButton):
        for c in w.findChildren(cls):
            t = c.text()
            if t and clean(t) != t:
                c.setText(clean(t))
    for le in w.findChildren(QtWidgets.QLineEdit):
        n = le.objectName().lower()
        if le.text() and (le.echoMode() != QtWidgets.QLineEdit.EchoMode.Normal or any(s in n for s in HIDE)):
            le.setText("••••••••")


async def snap_dialogs(prefix, opener, delay=1600, steps=None):
    """Oeffnet einen Dialog (auch modale), fotografiert alle neuen Fenster und schliesst sie wieder.

    steps: Liste (Knopftext, Dateisuffix): klickt im Dialog nacheinander diese Knoepfe und fotografiert jeweils.
    """
    before = set(app.topLevelWidgets())
    shots = []

    def grab_new():
        for w in app.topLevelWidgets():
            if w not in before and w.isVisible() and w.width() > 120:
                try:
                    dialog_scrub(w)
                    p = os.path.join(OUT, f"{prefix}.png")
                    w.grab().save(p)
                    shots.append(p)
                    print("saved", os.path.basename(p), flush=True)
                    for text, suffix in steps or []:
                        hit = None
                        for b in w.findChildren(QtWidgets.QAbstractButton):
                            if b.isVisible() and b.text().strip().lower() == text.lower():
                                hit = b
                                break
                        if hit is None:
                            for lst in w.findChildren(QtWidgets.QListWidget):
                                for i in range(lst.count()):
                                    if lst.item(i).text().strip().lower() == text.lower():
                                        lst.setCurrentRow(i)
                                        hit = lst
                                        break
                        else:
                            hit.click()
                        if hit is None:
                            print("step not found", prefix, text, flush=True)
                            continue
                        QtWidgets.QApplication.processEvents()
                        loop.call_later(0.0, lambda: None)
                        QtCore.QTimer.singleShot(0, lambda: None)
                        w.repaint()
                        dialog_scrub(w)
                        p2 = os.path.join(OUT, f"{prefix}_{suffix}.png")
                        w.grab().save(p2)
                        print("saved", os.path.basename(p2), flush=True)
                except Exception as exc:  # noqa: BLE001
                    print("grab failed", prefix, exc, flush=True)
                try:
                    w.close()
                except Exception:  # noqa: BLE001
                    pass

    QtCore.QTimer.singleShot(delay, grab_new)
    try:
        r = opener()
        if asyncio.iscoroutine(r):
            await r
    except Exception as exc:  # noqa: BLE001
        print("opener failed", prefix, exc, flush=True)
    await wait(delay + 900)
    for w in list(app.topLevelWidgets()):
        if w not in before and w.isVisible():
            try:
                w.close()
            except Exception:  # noqa: BLE001
                pass


def click(name):
    b = win.findChild(QtWidgets.QAbstractButton, name)
    if b is None:
        print("button not found", name, flush=True)
        return None
    b.click()
    return b


async def run():
    await wait(3500)
    await sig.set_main_tab()
    await wait(1500)
    stacks = {s.objectName(): s for s in win.findChildren(QtWidgets.QStackedWidget)}
    main = stacks["stackedWidget"]
    opt = [s for s in win.findChildren(QtWidgets.QStackedWidget) if s.count() >= 14][0]
    names = [main.widget(i).objectName() for i in range(main.count())]

    if WHAT in ("seiten", "alle"):
        for i, n in enumerate(names):
            if n in ("options_page", "chat_page", "charactersgateway_page"):
                continue
            main.setCurrentIndex(i)
            await snap(f"seite_{i}_{n.replace('_page', '')}")
        main.setCurrentIndex(names.index("charactersgateway_page"))
        await wait(4000)
        await snap("seite_galerie")

    if WHAT in ("optionen", "alle"):
        main.setCurrentIndex(names.index("options_page"))
        menu = ui.options_menu
        seen = set()
        for r in range(menu.count()):
            it = menu.item(r)
            if not (it.flags() & QtCore.Qt.ItemFlag.ItemIsSelectable):
                continue
            menu.setCurrentItem(it)          # wie ein Klick: die Menue-Auswahl bleibt zur Seite passend
            await wait(700)
            i = opt.currentIndex()
            if i in seen:
                continue
            seen.add(i)
            nm = opt.widget(i).objectName().replace("_tab", "")
            await snap(f"optionen_{i:02d}_{nm}")
            await snap_tall(f"optionen_{i:02d}_{nm}", opt.widget(i))

    if WHAT in ("dialoge", "alle"):
        main.setCurrentIndex(names.index("main_characters_page"))
        await wait(800)
        try:
            await sig.open_chat("Yume")
        except Exception as exc:  # noqa: BLE001
            print("open_chat failed", exc, flush=True)
        await wait(2500)
        await snap("chat_yume")
        for tag, opener, steps in (
            ("dialog_personas", sig.open_personas_editor, None),
            ("dialog_systemprompt", sig.open_system_prompt_editor, None),
            ("dialog_lorebook", sig.open_lorebook_editor, None),
            ("dialog_autorennotizen", sig.open_author_notes_editor, None),
            ("dialog_ki_assistent", sig.open_ai_character_assistant, None),
            ("dialog_stimme", lambda: sig.open_voice_menu("Yume"),
             [("ElevenLabs", "elevenlabs"), ("XTTSv2", "xtts"), ("Edge TTS", "edge"), ("Kokoro", "kokoro"), ("Silero (RU)", "silero"), ("Qwen-3 TTS", "qwen3")]),
            ("dialog_ausdruecke", lambda: sig.open_expressions_menu("Yume"),
             [("Ausdrucksbilder", "bilder"), ("Live2D-Modell", "live2d"), ("VRM-3D-Modell", "vrm")]),
            ("dialog_gedaechtnis", sig.open_soul_memory_viewer, None),
            ("dialog_bildgenerierung", sig.open_image_gen_settings, None),
        ):
            await snap_dialogs(tag, opener, steps=steps)

    if WHAT in ("chat", "alle"):
        main.setCurrentIndex(names.index("main_characters_page"))
        await wait(800)
        try:
            await sig.open_chat("Yume")
        except Exception as exc:  # noqa: BLE001
            print("open_chat failed", exc, flush=True)
        await wait(2500)
        for tag, objname in (
            ("chat_hintergrund", "pushButton_change_chat_background"),
            ("chat_autorennotizen", "pushButton_author_notes"),
            ("chat_zusammenfassung", "pushButton_summary"),
            ("chat_gedaechtnis", "pushButton_soul_memory"),
            ("chat_mehr", "pushButton_more"),
            ("chat_persona_wechseln", "pushButton_switch_persona"),
            ("chat_werkzeuge", "pushButton_toggle_tools"),
        ):
            await snap_dialogs(tag, lambda o=objname: click(o), delay=1500)
            await wait(400)

    if WHAT in ("buehne", "alle"):
        idx = names.index("soul_stage_page")
        main.setCurrentIndex(idx)
        await wait(1500)
        await snap("buehne_uebersicht")
        page = main.widget(idx)
        for b in page.findChildren(QtWidgets.QAbstractButton):
            if b.isVisible() and "neue szene" in b.text().lower():
                b.click()
                break
        await wait(1500)
        await snap("buehne_szene_bearbeiten")
        for sa in page.findChildren(QtWidgets.QScrollArea):
            w = sa.widget()
            if w is not None and w.height() > 1200:
                win.resize(1600, min(w.height() + 160, 5200))
                await wait(1400)
                scrub()
                win.grab().save(os.path.join(OUT, "buehne_szene_bearbeiten_voll.png"))
                print("saved buehne_szene_bearbeiten_voll", flush=True)
                win.resize(1600, 900)
                break

    if WHAT in ("werkstatt", "alle"):
        from PyQt6 import QtTest
        idx = names.index("rp_editors_page")
        main.setCurrentIndex(idx)
        await wait(1200)
        page = main.widget(idx)

        def click_card(title):
            for lbl in page.findChildren(QtWidgets.QLabel):
                if lbl.text().strip() == title:
                    w = lbl
                    while w is not None and w is not page:
                        QtTest.QTest.mouseClick(w, QtCore.Qt.MouseButton.LeftButton)
                        w = w.parentWidget()
                        break
                    return True
            print("card not found", title, flush=True)
            return False

        for tag, title in (("werkstatt_discord", "Discord-Gateway"), ("werkstatt_bildgenerierung", "Bildgenerierung")):
            await snap_dialogs(tag, lambda t_=title: click_card(t_), delay=1800)
            await wait(500)
            main.setCurrentIndex(idx)
            await wait(600)

    if WHAT in ("kacheln", "alle"):
        main.setCurrentIndex(names.index("main_characters_page"))
        await wait(1000)

        def click_text(txt):
            for b in win.findChildren(QtWidgets.QWidget):
                label = getattr(b, "text", None)
                try:
                    t_ = label() if callable(label) else ""
                except Exception:  # noqa: BLE001
                    t_ = ""
                if isinstance(t_, str) and t_.strip().lower() == txt.lower() and b.isVisible():
                    if hasattr(b, "click"):
                        b.click()
                        return True
            print("not found", txt, flush=True)
            return False

        await snap_dialogs("anruf_modus", lambda: click_text("Anrufen"), delay=1800)
        # Kachel mit Mauszeiger: zeigt die Aktionsleiste
        card = None
        for w in win.findChildren(QtWidgets.QWidget):
            if w.metaObject().className().startswith("CharacterCard") and w.isVisible():
                card = w
                break
        if card is not None:
            QtCore.QCoreApplication.sendEvent(card, QtCore.QEvent(QtCore.QEvent.Type.Enter))
            await wait(800)
            await snap("kachel_aktionen")

    if WHAT in ("about", "alle"):
        main.setCurrentIndex(names.index("main_characters_page"))
        await wait(800)
        await snap_dialogs("dialog_ueber", lambda: click("about_btn"), delay=1500)

    if WHAT == "web":
        # Startet Webclient (Port 8000) und Dashboard (Port 8765) fuer Browser-Aufnahmen und wartet.
        main.setCurrentIndex(names.index("main_characters_page"))
        await wait(800)
        await sig.open_chat("Yume")
        sig.on_toggle_web_server()
        from app.utils.dashboard_server import DashboardServer
        dash = DashboardServer(sig, "demo-token", host="127.0.0.1", port=8765, allow_lan=False)
        dash.start_in_thread()
        await wait(3000)
        print("READY web-token=" + sig.get_or_create_web_token(), flush=True)
        await wait(int(os.environ.get("YUME_WEB_SECONDS", "300")) * 1000)

    print("DONE", flush=True)
    app.quit()
    loop.stop()


asyncio.ensure_future(run())
with loop:
    loop.run_forever()
