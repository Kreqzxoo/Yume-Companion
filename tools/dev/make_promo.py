"""
Baut Werbematerial aus den Screenshots der Dokumentation:
  - social_preview_<lang>.png  (1280x640, GitHub "Social preview" und Link-Vorschau)
  - promo_vertical_<lang>.mp4  (1080x1920, fuer TikTok / Instagram Reels / YouTube Shorts, ohne Ton)
Aufruf:  python tools/dev/make_promo.py <Ausgabeordner> [ffmpeg.exe]
Die englische Fassung nutzt docs/images/en, die deutsche docs/images.
"""
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
IMG = ROOT / "docs" / "images"
FONTS = ROOT / "app" / "font"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "docs" / "images" / "promo")
FFMPEG = sys.argv[2] if len(sys.argv) > 2 else "ffmpeg"
OUT.mkdir(parents=True, exist_ok=True)
BG_TOP, BG_BOTTOM = (22, 14, 36), (70, 26, 84)
PINK = (255, 143, 199)
URL = "github.com/Kreqzxoo/Yume-Companion"


def font(size, bold=True):
    return ImageFont.truetype(str(FONTS / ("InterTight-ExtraBold.ttf" if bold else "InterTight-Medium.ttf")), size)


def gradient(w, h):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)))
    return img


def rounded(im, radius):
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=255)
    im.putalpha(mask)
    return im


def shadow_paste(canvas, im, xy, blur=30):
    sh = Image.new("RGBA", (im.width + 2 * blur, im.height + 2 * blur), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((blur, blur, blur + im.width, blur + im.height), 28, fill=(0, 0, 0, 190))
    sh = sh.filter(ImageFilter.GaussianBlur(blur / 2))
    canvas.alpha_composite(sh, (xy[0] - blur, xy[1] - blur + 14))
    canvas.alpha_composite(im, xy)


def wrap(draw, text, fnt, width):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def centered(draw, text, y, fnt, fill, width, maxw):
    for line in wrap(draw, text, fnt, maxw):
        draw.text(((width - draw.textlength(line, font=fnt)) / 2, y), line, font=fnt, fill=fill)
        y += int(fnt.size * 1.2)
    return y


# (picture, title, subtitle) per language; pictures are relative to docs/images (German) or docs/images/en (English)
SLIDES = {
    "en": [
        ("hero.png", "Yume Companion", "Your AI companion for PC and Android"),
        ("pc/chat_vrm_mika.png", "Characters that remember you", "Long-term memory, voice, Live2D and 3D VRM avatars"),
        ("android/04_chat_verbunden.png", "Chat and call from your phone", "The Android app talks to the AI on your PC"),
        ("android/13_assistent_startbildschirm.png", "Say the wake word", "She answers over any app, like a phone assistant"),
        ("pc/buehne_uebersicht.png", "Role-play with an AI game master", "Yume Stage: scenes, parties, lorebooks"),
        ("pc/optionen_18_organizer.png", "Calendar, mail, reminders, routines", "A companion that helps with your day"),
        ("llm-server/01_sprache.png", "Second PC as AI server", "Yume LLM Server: language, vision and image models"),
    ],
    "de": [
        ("hero.png", "Yume Companion", "Dein KI-Begleiter für PC und Android"),
        ("pc/chat_vrm_mika.png", "Charaktere, die sich an dich erinnern", "Langzeit-Gedächtnis, Stimme, Live2D- und 3D-VRM-Avatare"),
        ("android/04_chat_verbunden.png", "Chat und Anruf am Handy", "Die Android-App spricht mit der KI auf deinem PC"),
        ("android/13_assistent_startbildschirm.png", "Sag das Wake Word", "Sie antwortet über jeder App, wie ein Handy-Assistent"),
        ("pc/buehne_uebersicht.png", "Rollenspiel mit KI-Spielleiter", "Yume-Bühne: Szenen, Gruppen, Lorebooks"),
        ("pc/optionen_18_organizer.png", "Kalender, Mail, Erinnerungen, Routinen", "Eine Begleiterin, die dir im Alltag hilft"),
        ("llm-server/01_sprache.png", "Zweiter PC als KI-Server", "Yume LLM Server: Sprach-, Vision- und Bildmodelle"),
    ],
}
END = {
    "en": ("Free beta · open source PC app", "Windows 10/11 + Android 9+", "Get it on GitHub:", "Discord + Ko-fi: links on GitHub"),
    "de": ("Kostenlose Beta · PC-App quelloffen", "Windows 10/11 + Android 9+", "Jetzt auf GitHub:", "Discord + Ko-fi: Links auf GitHub"),
}


def src(lang, rel):
    return (IMG / "en" / rel) if lang == "en" else (IMG / rel)


def slide(lang, rel, title, subtitle):
    W, H = 1080, 1920
    canvas = gradient(W, H).convert("RGBA")
    d = ImageDraw.Draw(canvas)
    y = centered(d, title, 150, font(84), (255, 255, 255), W, 940)
    centered(d, subtitle, y + 14, font(44, False), PINK, W, 900)
    pic = Image.open(src(lang, rel)).convert("RGB")
    if pic.width < pic.height:                                   # phone screenshot
        h = 1180
        pic = pic.resize((round(pic.width * h / pic.height), h), Image.LANCZOS)
    else:                                                        # PC screenshot / wide image
        w = 960
        pic = pic.resize((w, round(pic.height * w / pic.width)), Image.LANCZOS)
    pic = rounded(pic, 34)
    shadow_paste(canvas, pic, ((W - pic.width) // 2, 640 + max(0, (1180 - pic.height) // 2)))
    d.text(((W - d.textlength(URL, font=font(40, False))) / 2, 1830), URL, font=font(40, False), fill=(215, 205, 235))
    return canvas.convert("RGB")


def end_slide(lang):
    W, H = 1080, 1920
    canvas = gradient(W, H).convert("RGBA")
    d = ImageDraw.Draw(canvas)
    logo = Image.open(IMG / "en" / "hero.png" if lang == "en" else IMG / "hero.png").convert("RGB")
    y = centered(d, "Yume Companion", 420, font(110), (255, 255, 255), W, 940)
    t1, t2, t3, t4 = END[lang]
    y = centered(d, t1, y + 40, font(52, False), PINK, W, 900)
    y = centered(d, t2, y + 20, font(46, False), (230, 220, 245), W, 900)
    y = centered(d, t3, y + 140, font(52, False), (230, 220, 245), W, 900)
    y = centered(d, URL, y + 10, font(60), (255, 255, 255), W, 1000)
    centered(d, t4, y + 90, font(44, False), PINK, W, 900)
    return canvas.convert("RGB")


def video(lang):
    tmp = OUT / f"_slides_{lang}"
    tmp.mkdir(exist_ok=True)
    files = []
    for i, (rel, title, sub) in enumerate(SLIDES[lang]):
        p = tmp / f"s{i}.png"
        slide(lang, rel, title, sub).save(p)
        files.append(p)
    p = tmp / "end.png"
    end_slide(lang).save(p)
    files.append(p)
    dur, fade = 3.4, 0.5
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    for f in files:
        cmd += ["-loop", "1", "-t", str(dur + fade), "-i", str(f)]
    parts, last = [], "[0:v]"
    for i in range(1, len(files)):
        out = f"[x{i}]"
        parts.append(f"{last}[{i}:v]xfade=transition=fade:duration={fade}:offset={i * dur - fade + fade * 0:.2f}{out}")
        last = out
    cmd += ["-filter_complex", ";".join(parts), "-map", last, "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "20",
            "-movflags", "+faststart", str(OUT / f"promo_vertical_{lang}.mp4")]
    subprocess.run(cmd, check=True)
    for f in files:
        f.unlink()
    tmp.rmdir()
    print("video", lang)


def social_preview(lang):
    W, H = 1280, 640
    canvas = gradient(W, H).convert("RGBA")
    d = ImageDraw.Draw(canvas)
    d.text((64, 70), "Yume Companion", font=font(84), fill=(255, 255, 255))
    sub = {"en": "AI companion for PC and Android", "de": "KI-Begleiter für PC und Android"}[lang]
    d.text((68, 172), sub, font=font(40, False), fill=PINK)
    bullets = {"en": ["Memory, voice, VRM avatars", "Android app + wake word", "Local models or own keys", "Free beta on GitHub"],
               "de": ["Gedächtnis, Stimme, VRM-Avatare", "Android-App + Wake Word", "Lokal oder mit eigenen Keys", "Kostenlose Beta auf GitHub"]}[lang]
    y = 270
    for b in bullets:
        d.text((68, y), "•  " + b, font=font(31, False), fill=(235, 228, 248))
        y += 58
    d.text((68, 570), URL, font=font(29, False), fill=(215, 205, 235))
    ph = Image.open(src(lang, "android/04_chat_verbunden.png")).convert("RGB")
    ph = rounded(ph.resize((round(ph.width * 560 / ph.height), 560), Image.LANCZOS), 30)
    shadow_paste(canvas, ph, (900, 40), blur=20)
    pc = Image.open(src(lang, "pc/chat_vrm_mika.png")).convert("RGB")
    pc = rounded(pc.resize((520, round(pc.height * 520 / pc.width)), Image.LANCZOS), 18)
    shadow_paste(canvas, pc, (630, 300), blur=20)
    canvas.convert("RGB").save(OUT / f"social_preview_{lang}.png", optimize=True)
    print("preview", lang)


if __name__ == "__main__":
    for lang in ("en", "de"):
        social_preview(lang)
        video(lang)
