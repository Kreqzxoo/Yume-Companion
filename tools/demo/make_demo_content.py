"""
Erzeugt Demo-Inhalte fuer Yume Companion: drei erfundene Beispiel-Charaktere mit selbst gezeichneten
Ausdrucksbildern (PNG). Alles ist eigenes, freies Material (CC0) und eignet sich fuer Screenshots und Tests.

Aufruf (im Projektordner, mit der Python-Umgebung von Yume Companion):
    python tools/demo/make_demo_content.py

Schreibt:
    assets/emotions/images/<Charakter>/<emotion>.png
    app/cache/avatars/<Charakter>_avatar.png (ueber die App-Funktion)
    app/configuration/characters.json (nur die drei Demo-Figuren)
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

EN = os.environ.get("YUME_DEMO_LANG") == "en"   # English demo content (for the English docs)


def L(de, en):
    return en if EN else de


W, H, SS = 512, 640, 3  # Zielgroesse, Supersampling


def _pt(v):
    return int(v * SS)


def draw_face(path, hair, eyes, skin=(255, 228, 214), outfit=(120, 120, 200), emotion="neutral"):
    im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cx = W / 2

    # Haare hinten
    d.ellipse([_pt(cx - 190), _pt(70), _pt(cx + 190), _pt(480)], fill=hair)
    d.rounded_rectangle([_pt(cx - 190), _pt(260), _pt(cx + 190), _pt(560)], radius=_pt(80), fill=hair)
    # Koerper
    d.rounded_rectangle([_pt(cx - 120), _pt(470), _pt(cx + 120), _pt(660)], radius=_pt(60), fill=outfit)
    d.rectangle([_pt(cx - 28), _pt(430), _pt(cx + 28), _pt(500)], fill=skin)
    # Gesicht
    d.ellipse([_pt(cx - 135), _pt(150), _pt(cx + 135), _pt(450)], fill=skin)
    # Pony
    d.pieslice([_pt(cx - 150), _pt(95), _pt(cx + 150), _pt(330)], 180, 360, fill=hair)
    for off in (-90, -30, 35, 95):
        d.polygon([(_pt(cx + off - 28), _pt(210)), (_pt(cx + off + 28), _pt(210)), (_pt(cx + off), _pt(285))], fill=hair)

    ey = 335
    ex = 62
    dark = (50, 40, 60)

    def eye(x, kind):
        if kind == "closed_happy":  # ^ ^
            d.arc([_pt(x - 30), _pt(ey - 22), _pt(x + 30), _pt(ey + 26)], 200, 340, fill=dark, width=_pt(7))
        elif kind == "closed_sad":
            d.arc([_pt(x - 30), _pt(ey - 6), _pt(x + 30), _pt(ey + 38)], 20, 160, fill=dark, width=_pt(7))
        elif kind == "angry":
            d.ellipse([_pt(x - 26), _pt(ey - 22), _pt(x + 26), _pt(ey + 30)], fill=(255, 255, 255), outline=dark, width=_pt(4))
            d.ellipse([_pt(x - 17), _pt(ey - 12), _pt(x + 17), _pt(ey + 26)], fill=eyes)
            d.ellipse([_pt(x - 8), _pt(ey - 2), _pt(x + 8), _pt(ey + 16)], fill=dark)
        elif kind == "wide":
            d.ellipse([_pt(x - 32), _pt(ey - 34), _pt(x + 32), _pt(ey + 36)], fill=(255, 255, 255), outline=dark, width=_pt(4))
            d.ellipse([_pt(x - 18), _pt(ey - 18), _pt(x + 18), _pt(ey + 24)], fill=eyes)
            d.ellipse([_pt(x - 8), _pt(ey - 6), _pt(x + 8), _pt(ey + 12)], fill=dark)
            d.ellipse([_pt(x - 2), _pt(ey - 16), _pt(x + 10), _pt(ey - 4)], fill=(255, 255, 255))
        elif kind == "heart":
            d.ellipse([_pt(x - 28), _pt(ey - 22), _pt(x + 2), _pt(ey + 6)], fill=(235, 80, 120))
            d.ellipse([_pt(x - 2), _pt(ey - 22), _pt(x + 28), _pt(ey + 6)], fill=(235, 80, 120))
            d.polygon([(_pt(x - 28), _pt(ey - 6)), (_pt(x + 28), _pt(ey - 6)), (_pt(x), _pt(ey + 30))], fill=(235, 80, 120))
        else:  # normal
            d.ellipse([_pt(x - 28), _pt(ey - 28), _pt(x + 28), _pt(ey + 32)], fill=(255, 255, 255), outline=dark, width=_pt(4))
            d.ellipse([_pt(x - 19), _pt(ey - 18), _pt(x + 19), _pt(ey + 26)], fill=eyes)
            d.ellipse([_pt(x - 9), _pt(ey - 6), _pt(x + 9), _pt(ey + 14)], fill=dark)
            d.ellipse([_pt(x - 3), _pt(ey - 14), _pt(x + 9), _pt(ey - 2)], fill=(255, 255, 255))

    kinds = {
        "neutral": "normal", "joy": "closed_happy", "love": "heart", "sadness": "closed_sad",
        "anger": "angry", "surprise": "wide", "embarrassment": "normal", "curiosity": "wide",
    }
    k = kinds.get(emotion, "normal")
    eye(cx - ex, k)
    eye(cx + ex, k)

    # Augenbrauen
    brow = dark
    if emotion == "anger":
        d.line([_pt(cx - 100), _pt(ey - 50), _pt(cx - 30), _pt(ey - 30)], fill=brow, width=_pt(7))
        d.line([_pt(cx + 100), _pt(ey - 50), _pt(cx + 30), _pt(ey - 30)], fill=brow, width=_pt(7))
    elif emotion == "sadness":
        d.line([_pt(cx - 100), _pt(ey - 30), _pt(cx - 30), _pt(ey - 48)], fill=brow, width=_pt(6))
        d.line([_pt(cx + 100), _pt(ey - 30), _pt(cx + 30), _pt(ey - 48)], fill=brow, width=_pt(6))
    elif emotion in ("surprise", "curiosity"):
        d.arc([_pt(cx - 100), _pt(ey - 78), _pt(cx - 30), _pt(ey - 40)], 200, 340, fill=brow, width=_pt(6))
        d.arc([_pt(cx + 30), _pt(ey - 78), _pt(cx + 100), _pt(ey - 40)], 200, 340, fill=brow, width=_pt(6))
    else:
        d.arc([_pt(cx - 100), _pt(ey - 66), _pt(cx - 30), _pt(ey - 34)], 200, 340, fill=brow, width=_pt(5))
        d.arc([_pt(cx + 30), _pt(ey - 66), _pt(cx + 100), _pt(ey - 34)], 200, 340, fill=brow, width=_pt(5))

    # Wangen
    if emotion in ("joy", "love", "embarrassment"):
        for x in (cx - 95, cx + 95):
            d.ellipse([_pt(x - 30), _pt(ey + 42), _pt(x + 30), _pt(ey + 72)], fill=(255, 150, 160, 150))
    # Traenen
    if emotion == "sadness":
        for x in (cx - ex - 10, cx + ex + 10):
            d.ellipse([_pt(x - 7), _pt(ey + 38), _pt(x + 7), _pt(ey + 70)], fill=(140, 200, 255, 200))

    # Mund
    my = 408
    mouth = (190, 80, 90)
    if emotion in ("joy", "love"):
        d.pieslice([_pt(cx - 34), _pt(my - 22), _pt(cx + 34), _pt(my + 30)], 0, 180, fill=mouth)
    elif emotion == "sadness":
        d.arc([_pt(cx - 26), _pt(my), _pt(cx + 26), _pt(my + 36)], 200, 340, fill=mouth, width=_pt(6))
    elif emotion == "anger":
        d.line([_pt(cx - 26), _pt(my + 8), _pt(cx + 26), _pt(my + 8)], fill=mouth, width=_pt(7))
    elif emotion in ("surprise", "curiosity"):
        d.ellipse([_pt(cx - 14), _pt(my - 10), _pt(cx + 14), _pt(my + 24)], fill=mouth)
    elif emotion == "embarrassment":
        d.line([_pt(cx - 20), _pt(my + 6), _pt(cx - 6), _pt(my + 14), ], fill=mouth, width=_pt(6))
        d.line([_pt(cx - 6), _pt(my + 14), _pt(cx + 6), _pt(my + 4)], fill=mouth, width=_pt(6))
        d.line([_pt(cx + 6), _pt(my + 4), _pt(cx + 20), _pt(my + 12)], fill=mouth, width=_pt(6))
    else:
        d.arc([_pt(cx - 22), _pt(my - 14), _pt(cx + 22), _pt(my + 18)], 20, 160, fill=mouth, width=_pt(6))

    im = im.resize((W, H), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)


VRM_SAMPLES = {"Mika": "Anime Girl.vrm", "Kai": "Anime Man.vrm"}

CHARACTERS = [
    {
        "name": "Yume",
        "folder": "Yume-Demo",
        "hair": (176, 136, 235), "eyes": (110, 90, 220), "outfit": (95, 80, 190),
        "title": L("Deine ruhige KI-Begleiterin", "Your calm AI companion"),
        "description": L("Yume ist eine freundliche, aufmerksame KI-Begleiterin. Sie merkt sich, was dir wichtig ist, und erinnert dich sanft an Dinge.", "Yume is a friendly, attentive AI companion. She remembers what matters to you and gently reminds you of things."),
        "personality": L("warmherzig, neugierig, ruhig, ein bisschen verspielt; spricht Deutsch, kurz und natuerlich", "warm-hearted, curious, calm, a little playful; speaks English, short and natural"),
        "scenario": L("Yume leistet dir am PC Gesellschaft, hilft im Alltag und plaudert mit dir.", "Yume keeps you company at the PC, helps with everyday things and chats with you."),
        "first_message": L("Hallo! Schoen, dass du da bist. Wie war dein Tag bisher?", "Hello! Nice to see you. How was your day so far?"),
        "examples": L("{{user}}: Ich bin muede.\n{{char}}: Dann goenn dir eine kurze Pause. Soll ich dich in zehn Minuten erinnern?", "{{user}}: I am tired.\n{{char}}: Then take a short break. Shall I remind you in ten minutes?"),
    },
    {
        "name": "Mika",
        "folder": "Mika-Demo",
        "hair": (255, 160, 120), "eyes": (70, 170, 140), "outfit": (230, 110, 110),
        "title": L("Fröhliche Spiele-Freundin", "Cheerful gaming friend"),
        "description": L("Mika liebt Videospiele, Snacks und schlechte Witze. Sie feuert dich an, egal ob beim Zocken oder Lernen.", "Mika loves video games, snacks and bad jokes. She cheers you on, whether gaming or studying."),
        "personality": L("energiegeladen, humorvoll, loyal, leicht chaotisch", "energetic, humorous, loyal, slightly chaotic"),
        "scenario": L("Mika sitzt neben dir und kommentiert dein Spiel.", "Mika sits next to you and comments on your game."),
        "first_message": L("Yo! Startest du gleich eine Runde? Ich hab schon Snacks geholt!", "Yo! Are you starting a round soon? I already got snacks!"),
        "examples": L("{{user}}: Ich hab verloren.\n{{char}}: Nicht schlimm, Revanche! Diesmal klappt es.", "{{user}}: I lost.\n{{char}}: No big deal, rematch! This time it will work."),
    },
    {
        "name": "Kai",
        "folder": "Kai-Demo",
        "hair": (70, 90, 120), "eyes": (120, 180, 220), "outfit": (60, 110, 140),
        "title": L("Ruhiger Lern-Coach", "Calm study coach"),
        "description": L("Kai erklaert Dinge geduldig und strukturiert. Er hilft beim Lernen, Planen und Programmieren.", "Kai explains things patiently and in a structured way. He helps with studying, planning and programming."),
        "personality": L("ruhig, sachlich, geduldig, trocken-humorvoll", "calm, matter-of-fact, patient, dry humour"),
        "scenario": L("Kai begleitet dich beim Lernen und beim Organisieren deiner Aufgaben.", "Kai accompanies you while studying and organising your tasks."),
        "first_message": L("Hi. Woran arbeiten wir heute? Ich helfe dir, es in kleine Schritte zu teilen.", "Hi. What are we working on today? I will help you split it into small steps."),
        "examples": L("{{user}}: Ich verstehe Rekursion nicht.\n{{char}}: Fangen wir mit einem kleinen Beispiel an: eine Funktion, die sich selbst aufruft.", "{{user}}: I do not understand recursion.\n{{char}}: Let us start with a small example: a function that calls itself."),
    },
]

EMOTIONS = ["neutral", "joy", "love", "sadness", "anger", "surprise", "embarrassment", "curiosity"]


def main():
    for c in CHARACTERS:
        folder = os.path.join("assets", "emotions", "images", c["folder"])
        for e in EMOTIONS:
            draw_face(os.path.join(folder, f"{e}.png"), c["hair"], c["eyes"], outfit=c["outfit"], emotion=e)
        # Weitere Zustaende nutzen das neutrale Bild als Rueckfall
        print("Bilder:", folder)

    from app.configuration.configuration import ConfigurationCharacters
    cfg = ConfigurationCharacters()
    cfg.save_configuration_edit({"character_list": {}})
    for c in CHARACTERS:
        avatar = os.path.join("assets", "emotions", "images", c["folder"], "neutral.png")
        cfg.save_character_card(
            character_name=c["name"], character_title=c["title"], character_avatar=avatar,
            character_description=c["description"], character_personality=c["personality"],
            first_message=c["first_message"], scenario=c["scenario"], example_messages=c["examples"],
            alternate_greetings=[], selected_persona="None", selected_system_prompt_preset="By default",
            selected_lorebook="None", elevenlabs_voice_id=None, voice_type=None, rvc_enabled=False,
            rvc_file=None, expression_images_folder=os.path.join("assets", "emotions", "images", c["folder"]),
            live2d_model_folder=None, vrm_model_file=None, conversation_method="Local LLM",
        )
        print("Charakter:", c["name"])
        if c["name"] in ("Yume", "Mika"):  # Avatar-Modus "Ausdrucksbilder" einschalten (Bilder siehe oben)
            data = cfg.load_configuration()
            data["character_list"][c["name"]]["current_sow_system_mode"] = "Expressions Images"
            cfg.save_configuration_edit(data)
        vrm = VRM_SAMPLES.get(c["name"])  # 3D-Avatar: die zwei VRoid-Beispielmodelle aus assets/emotions/vrm
        if vrm and os.path.exists(os.path.join("assets", "emotions", "vrm", vrm)):
            data = cfg.load_configuration()
            data["character_list"][c["name"]]["current_sow_system_mode"] = "VRM"
            data["character_list"][c["name"]]["vrm_model_file"] = os.path.join(os.getcwd(), "assets", "emotions", "vrm", vrm)
            cfg.save_configuration_edit(data)

    # Kurzes Beispielgespraech fuer Yume (nur fuer Screenshots / Demo)
    import uuid
    talk = [
        (True, L("Hey Yume, ich habe gleich einen langen Tag. Kannst du mich an meine Termine erinnern?", "Hey Yume, I have a long day ahead. Can you remind me of my appointments?")),
        (False, L("*lächelt* Natürlich! Du hast um 10:00 Uhr dein Team-Meeting und um 15:30 Uhr den Zahnarzt. Soll ich dich 20 Minuten vorher erinnern?", "*smiles* Of course! You have your team meeting at 10:00 and the dentist at 15:30. Shall I remind you 20 minutes before?")),
        (True, L("Ja, bitte. Und setz Milch und Brot auf die Einkaufsliste.", "Yes, please. And put milk and bread on the shopping list.")),
        (False, L("Erledigt. Milch und Brot stehen auf der Einkaufsliste. Viel Erfolg heute, du schaffst das!", "Done. Milk and bread are on the shopping list. Good luck today, you can do it!")),
    ]
    for is_user, text in talk:
        cfg.add_message_to_config("Yume", L("Du", "You") if is_user else "Yume", is_user, text, str(uuid.uuid4()))

    talk_mika = [
        (True, L("Hi Mika! Welches Spiel zocken wir heute Abend?", "Hi Mika! Which game are we playing tonight?")),
        (False, L("*grinst* Ich dachte an Kart-Rennen! Aber Vorsicht, ich bin heute in Topform und habe Snacks als Doping.", "*grins* I was thinking kart racing! But careful, I am in top form today and have snacks as doping.")),
        (True, L("Challenge accepted. Wer verliert, holt die Getränke.", "Challenge accepted. Whoever loses gets the drinks.")),
        (False, L("Abgemacht! Ich fange schon mal an, die Strecke auszusuchen. Regenbogenpfad, oder wagst du dich an den Vulkan?", "Deal! I will start picking the track. Rainbow Road, or do you dare try the Volcano?")),
    ]
    for is_user, text in talk_mika:
        cfg.add_message_to_config("Mika", L("Du", "You") if is_user else "Mika", is_user, text, str(uuid.uuid4()))


def demo_extras():
    """Beispiel-Persona, Lorebook und Autorennotizen (nur fuer Screenshots / Demo)."""
    from app.configuration.configuration import ConfigurationSettings
    st = ConfigurationSettings()
    st.update_user_data("personas", {
        "Alex": {"user_name": "Alex", "user_description": L("Alex ist Student, mag Technik, Spiele und Kaffee und spricht gern locker.", "Alex is a student who likes tech, games and coffee and enjoys a casual tone.")},
    })
    st.update_user_data("default_persona", "Alex")
    st.update_lorebook("Yume-Welt", {
        "name": "Yume-Welt",
        "description": L("Beispiel-Weltwissen für die Demo", "Example world knowledge for the demo"),
        "n_depth": 3,
        "entries": [
            {"name": L("Das Café", "The café"), "uid": 0, "key": ["Café", "Kaffee"], "exclude_key": [], "trigger_type": "keyword",
             "content": L("Das kleine Café an der Ecke heißt 'Sternschnuppe'. Yume empfiehlt dort den Kirschkuchen.", "The little café on the corner is called 'Shooting Star'. Yume recommends the cherry cake there."),
             "probability": 100, "sticky": 2, "cooldown": 0, "delay": 0, "injection_behavior": "passive"},
            {"name": L("Regeln des Hauses", "House rules"), "uid": 1, "key": [], "exclude_key": [], "trigger_type": "always_on",
             "content": L("Yume spricht Deutsch, antwortet kurz und erinnert sanft an Pausen.", "Yume speaks English, answers briefly and gently reminds of breaks."),
             "probability": 100, "sticky": 0, "cooldown": 0, "delay": 0, "injection_behavior": "active"},
            {"name": L("Regentage", "Rainy days"), "uid": 2, "key": [], "exclude_key": [], "trigger_type": "semantic",
             "content": L("Bei Regen schlägt Yume Tee und einen ruhigen Filmabend vor.", "When it rains, Yume suggests tea and a quiet movie night."),
             "probability": 100, "sticky": 0, "cooldown": 3, "delay": 0, "injection_behavior": "passive",
             "semantic_description": L("Es regnet, das Wetter ist grau und gemütlich.", "It is raining, the weather is grey and cosy.")},
        ],
    })


def demo_scene():
    """Beispiel-Szene fuer die Yume-Buehne (nur fuer Screenshots / Demo)."""
    import json
    folder = os.path.join(ROOT, ".soul_stage")
    os.makedirs(folder, exist_ok=True)
    scene = {
        "title": L("Das Café Sternschnuppe", "Café Shooting Star"),
        "description": L("Ein ruhiger Abend in einem kleinen Café – mit Yume und Mika.", "A quiet evening in a small café – with Yume and Mika."),
        "world_context": L("Ein gemütliches Café in einer Kleinstadt. Draußen regnet es leicht. Yume arbeitet hinter dem Tresen, Mika sitzt am Fenster.", "A cosy café in a small town. It is raining lightly outside. Yume works behind the counter, Mika sits by the window."),
        "starting_location": L("Café Sternschnuppe", "Café Shooting Star"),
        "time_of_day": "evening",
        "opening_narration": L("Der Regen trommelt leise gegen die Scheibe, als du die Tür aufschiebst. Es riecht nach Kaffee und frischem Kuchen.", "The rain drums softly against the window as you push the door open. It smells of coffee and fresh cake."),
        "first_message": "",
        "party": ["Yume", "Mika"],
        "gm_tone": "slice_of_life",
        "narrator_style": "Standard evocative present-tense prose",
        "conversation_method": "Local LLM",
        "persona": "Alex",
        "lorebook": [],
        "lock_bg": False,
        "disable_ambient": False,
    }
    with open(os.path.join(folder, "scenes.json"), "w", encoding="utf-8") as fh:
        json.dump({"scenes": {"demo-cafe": scene}}, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
    demo_extras()
    demo_scene()
