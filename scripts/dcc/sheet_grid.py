"""Draw a labelled coordinate grid over a sheet template so field positions
can be read off a preview when writing a layout for ttrpgtools.sheetfill.

    python scripts/dcc/sheet_grid.py template.pdf out.png [page] [dpi] [step]
    python scripts/dcc/sheet_grid.py template.png out.png

PDF coordinates are PDF points, origin bottom-left (what the layout uses).
PNG coordinates are pixels, origin top-left.
"""
import subprocess, sys, tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    page = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 100
    step = int(sys.argv[5]) if len(sys.argv) > 5 else 25
    if src.suffix.lower() == ".pdf":
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-f", str(page + 1), "-l", str(page + 1), str(src), f"{tmp}/p"], check=True)
            img = Image.open(next(Path(tmp).glob("p*.png"))).convert("RGB")
        scale = dpi / 72.0  # pixels per point
        to_px = lambda pt_x, pt_y: (pt_x * scale, img.height - pt_y * scale)
        w_pt, h_pt = img.width / scale, img.height / scale
    else:
        img = Image.open(src).convert("RGB")
        scale, w_pt, h_pt = 1.0, img.width, img.height
        to_px = lambda x, y: (x, y)
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(0, int(w_pt) + 1, step):
        px = to_px(x, 0)[0]
        major = x % (step * 4) == 0
        d.line([(px, 0), (px, img.height)], fill=(255, 0, 0, 140 if major else 60), width=1)
        if major:
            d.text((px + 2, 2), str(x), fill=(200, 0, 0, 255))
    for y in range(0, int(h_pt) + 1, step):
        py = to_px(0, y)[1]
        major = y % (step * 4) == 0
        d.line([(0, py), (img.width, py)], fill=(0, 0, 255, 140 if major else 60), width=1)
        if major:
            d.text((2, py + 2), str(y), fill=(0, 0, 200, 255))
    img.save(out)
    print(f"wrote {out} ({img.width}x{img.height}px, {w_pt:.0f}x{h_pt:.0f} units, step {step})")


if __name__ == "__main__":
    main()
