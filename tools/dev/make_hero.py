"""
Baut die Titelbilder fuer die README aus den vorhandenen Screenshots (docs/images).
Aufruf:  python tools/dev/make_hero.py
Erzeugt: docs/images/hero.png (Collage) und docs/images/galerie_*.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

IMG = Path(__file__).resolve().parent.parent.parent / "docs" / "images"
BG_TOP, BG_BOTTOM = (22, 14, 36), (58, 24, 70)


def gradient(w, h):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = c
    return img


def rounded(im, radius):
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=255)
    im.putalpha(mask)
    return im


def shadow_paste(canvas, im, xy, blur=24, offset=(0, 14)):
    sh = Image.new("RGBA", (im.width + 2 * blur, im.height + 2 * blur), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((blur, blur, blur + im.width, blur + im.height), 20, fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(blur / 2))
    canvas.alpha_composite(sh, (xy[0] - blur + offset[0], xy[1] - blur + offset[1]))
    canvas.alpha_composite(im, xy)


def load(rel, width=None, height=None):
    im = Image.open(IMG / rel).convert("RGB")
    if width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    if height:
        im = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    return im


def hero():
    w, h = 2040, 900
    canvas = gradient(w, h).convert("RGBA")
    pc = rounded(load("pc/chat_yume.png", width=1220), 18)
    shadow_paste(canvas, pc, (40, 120))
    ph1 = rounded(load("android/04_chat_verbunden.png", height=680), 36)
    ph2 = rounded(load("android/09_im_gespraech.png", height=740), 36)
    shadow_paste(canvas, ph1, (1310, 150))
    shadow_paste(canvas, ph2, (1660, 80))
    canvas.convert("RGB").save(IMG / "hero.png", optimize=True)


def gallery(name, files, cols, cell_w):
    ims = [load(f, width=cell_w) for f in files]
    rows = [ims[i:i + cols] for i in range(0, len(ims), cols)]
    gap = 24
    row_h = [max(i.height for i in r) for r in rows]
    w = cols * cell_w + (cols + 1) * gap
    h = sum(row_h) + (len(rows) + 1) * gap
    canvas = gradient(w, h).convert("RGBA")
    y = gap
    for r, rh in zip(rows, row_h):
        x = gap
        for im in r:
            shadow_paste(canvas, rounded(im, 14), (x, y), blur=14, offset=(0, 8))
            x += cell_w + gap
        y += rh + gap
    canvas.convert("RGB").save(IMG / name, optimize=True)


if __name__ == "__main__":
    hero()
    gallery("galerie_pc.png", [
        "pc/seite_1_main_characters.png", "pc/chat_gedaechtnis.png",
        "pc/buehne_uebersicht.png", "pc/optionen_02_llm.png",
        "web/dashboard_oben.png", "pc/optionen_18_organizer.png",
    ], cols=2, cell_w=900)
    gallery("galerie_android.png", [
        "android/04_chat_verbunden.png", "android/09_im_gespraech.png", "android/10_wandmodus.png",
        "android/11_auto_modus.png", "android/06_offline_notfallmodus.png",
    ], cols=5, cell_w=360)
    print("fertig")
