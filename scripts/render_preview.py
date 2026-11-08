"""Optional source renderer for the bundled PNG brand assets (requires Pillow).

Publishing uses the checked-in PNGs, not this script. Run from any directory:
    python scripts/render_preview.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUTPUT = Path(__file__).resolve().parents[1] / "web_preview"
BG = "#111917"
MINT = "#72D9C2"
WHITE = "#F1F6F3"
MUTED = "#B6C8C1"
SCALE = 2


def font(size, bold=False):
    return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size * SCALE)


def cube(draw, origin, size):
    """Draw a precise 3×3 cube with separate sticker faces and dark seams."""
    ox, oy = origin
    width, rise, height = size
    faces = [
        ((ox, oy), (width, rise), (-width, rise), "#EEF4EF", "#E2EAE4"),
        ((ox - 3 * width, oy + 3 * rise), (width, rise), (0, height), "#30967E", "#257C69"),
        ((ox, oy + 6 * rise), (width, -rise), (0, height), "#C26565", "#AD5355"),
    ]
    for (x, y), (ax, ay), (bx, by), color, alt in faces:
        for row in range(3):
            for col in range(3):
                points = []
                for u, v in ((.045, .045), (.955, .045), (.955, .955), (.045, .955)):
                    points.append(((x + ax * (col + u) + bx * (row + v)) * SCALE,
                                   (y + ay * (col + u) + by * (row + v)) * SCALE))
                draw.polygon(points, fill=alt if (row + col) % 3 == 1 else color,
                             outline="#0B1210", width=2 * SCALE)


def mark(draw, x, y, size, color=MINT):
    points = [(x, y), (x + size * .86, y + size * .5), (x + size * .86, y + size * 1.5),
              (x, y + size * 2), (x - size * .86, y + size * 1.5),
              (x - size * .86, y + size * .5), (x, y)]
    draw.line([(a * SCALE, b * SCALE) for a, b in points], fill=color,
              width=max(2, int(size * .13 * SCALE)), joint="curve")
    for end in ((x, y + size * 2), (x - size * .86, y + size * .5), (x + size * .86, y + size * .5)):
        draw.line([(x * SCALE, (y + size) * SCALE), (end[0] * SCALE, end[1] * SCALE)],
                  fill=color, width=max(2, int(size * .12 * SCALE)))


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1200 * SCALE, 630 * SCALE), BG)
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            glow = max(0, 1 - ((x / SCALE - 995) ** 2 / 600 ** 2 + (y / SCALE - 280) ** 2 / 550 ** 2))
            pixels[x, y] = (17 + int(8 * glow), 25 + int(19 * glow), 23 + int(14 * glow))
    draw = ImageDraw.Draw(image)

    def text(x, y, value, size, fill=WHITE, bold=False):
        draw.text((x * SCALE, y * SCALE), value, font=font(size, bold), fill=fill)

    mark(draw, 82, 65, 18)
    text(119, 66, "BLD LETTER MEMO", 23, MINT, True)
    text(64, 177, "Build your memo.", 49, bold=True)
    text(64, 243, "Train your recall.", 49, bold=True)
    text(66, 334, "Your workspace for blindfolded", 24, MUTED)
    text(66, 371, "3×3 cube training.", 24, MUTED)

    pills = [("Letter schemes", 188), ("Memo practice", 186), ("3-style algs", 159)]
    x = 64
    for label, width in pills:
        draw.rounded_rectangle((x * SCALE, 475 * SCALE, (x + width) * SCALE, 521 * SCALE),
                               radius=12 * SCALE, fill="#1E3430", outline="#37584D", width=SCALE)
        text(x + 16, 486, label, 18, MINT)
        x += width + 12
    cube(draw, (949, 143), (55, 19, 73))
    text(66, 574, "SCHEMES  /  PRACTICE  /  ANALYZE", 14, "#89A79A", True)
    image.resize((1200, 630), Image.Resampling.LANCZOS).save(OUTPUT / "share-card-v1.png", optimize=True)

    icon = Image.new("RGB", (512 * SCALE, 512 * SCALE), BG)
    mark(ImageDraw.Draw(icon), 256, 119, 132)
    for size, name in [(512, "app-icon-512.png"), (192, "app-icon-192.png"), (64, "favicon.png")]:
        icon.resize((size, size), Image.Resampling.LANCZOS).save(OUTPUT / name, optimize=True)
    print(f"Rendered preview assets in {OUTPUT}")


if __name__ == "__main__":
    main()
