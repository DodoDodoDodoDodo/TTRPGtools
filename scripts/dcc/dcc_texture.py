#!/usr/bin/env python3
"""Bake the paper tiles of the DCC pages from two material sets (colour, normal and displacement maps).

    python3 scripts/dcc/dcc_texture.py <folder holding Paper002_4K-JPG and Paper001_4K-PNG> [strength]

A tile is what lies over a flat palette colour, blended "hard-light" (static/dcc.css): mid-grey leaves the colour
exactly as it is, darker darkens, lighter lightens. So a tile is built around mid-grey from three parts:

  relief    the normal map, lit by one lamp from the top left; a turned piece is lit by the same lamp
  hollows   the displacement map: what lies deeper is a little darker
  flecks    the colour map: fibres and specks, with their own colour toned down

``strength`` scales all three (default 1.0). The roughness map is not used: flat page colours have no gloss.

Writes into ttrpgtools/web/static/dcc/textures/ (SETS below):
  sheet.webp, sheet-1 ... -6.webp   Paper002: the land colour, and one piece per panel
  card-1 ... -4.webp                Paper001: darker fields that lie on a panel (stat boxes, notes, buttons)
Every piece is cut from another part of the map and turned by another small angle, so neighbouring fields look
like separate pieces of paper. Tiles are shown at half their pixel size, to stay sharp on dense screens.
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageStat

Image.MAX_IMAGE_PIXELS = None
OUT = Path(__file__).resolve().parents[2] / "ttrpgtools" / "web" / "static" / "dcc" / "textures"
LAMP = (-0.5, 0.5, 0.707)   # towards the lamp: left, up, out of the page

# name -> folder, file ending, how strongly each part shows, and the tiles: (file, edge in px, degrees turned, centre of the cut)
SETS = {
    "sheet": {"folder": "Paper002_4K-JPG", "ending": "jpg", "relief": 0.28, "hollows": 0.25, "flecks": 0.4, "fleck_colour": 0.5, "seam": 160,
              "tiles": [("sheet", 1024, 0, (1660, 2140)),
                        ("sheet-1", 768, -14, (800, 800)), ("sheet-2", 768, -8, (2500, 900)), ("sheet-3", 768, -3, (900, 2100)),
                        ("sheet-4", 768, 4, (2400, 2200)), ("sheet-5", 768, 9, (800, 3400)), ("sheet-6", 768, 15, (2500, 3400))]},
    "card": {"folder": "Paper001_4K-PNG", "ending": "png", "relief": 0.5, "hollows": 0.1, "flecks": 0.3, "fleck_colour": 0.0, "seam": 128,
             "tiles": [("card-1", 512, -11, (460, 800)), ("card-2", 512, -4, (1060, 780)), ("card-3", 512, 6, (1660, 810)), ("card-4", 512, 13, (2260, 790))]},
}


def around_grey(img: Image.Image, factor: float) -> Image.Image:
    """Stretch or flatten an image around mid-grey."""
    return img.point(lambda v: max(0, min(255, round(128 + (v - 128) * factor))))


def high_pass(img: Image.Image, radius: int) -> Image.Image:
    """Keep the detail, drop slow changes of brightness and the base colour: the result sits around mid-grey."""
    return ImageChops.add(img, ImageChops.invert(img.filter(ImageFilter.GaussianBlur(radius))), scale=1, offset=-127)


def seamless(img: Image.Image, tile: int, seam: int) -> Image.Image:
    """Fade the strip beyond each edge over the opposite edge, so the tile repeats without a visible line."""
    out = img.crop((0, 0, tile, img.height))
    ramp = Image.linear_gradient("L").rotate(90, expand=True).resize((seam, img.height))  # 0 at the left, 255 at the right
    out.paste(Image.composite(img.crop((0, 0, seam, img.height)), img.crop((tile, 0, tile + seam, img.height)), ramp), (0, 0))
    img, out = out, out.crop((0, 0, tile, tile))
    ramp = Image.linear_gradient("L").resize((tile, seam))                                # 0 at the top, 255 at the bottom
    out.paste(Image.composite(img.crop((0, 0, tile, seam)), img.crop((0, tile, tile, tile + seam)), ramp), (0, 0))
    return out


def bake(maps: dict, spec: dict, tile: int, angle: float, centre: tuple[int, int], strength: float) -> Image.Image:
    side = tile + spec["seam"]
    turn = math.radians(angle)
    big = math.ceil(side * (abs(math.cos(turn)) + abs(math.sin(turn)))) + 4   # room to turn the cut without empty corners
    box = (centre[0] - big // 2, centre[1] - big // 2, centre[0] - big // 2 + big, centre[1] - big // 2 + big)
    width, height = maps["normal"].size
    assert box[0] >= 0 and box[1] >= 0 and box[2] <= width and box[3] <= height, f"the cut {box} reaches outside the {width} x {height} map"
    # the lamp stays where it is while the piece is turned (counter-clockwise for a positive angle; the map's green axis points up)
    lamp_x = LAMP[0] * math.cos(turn) + LAMP[1] * math.sin(turn)
    lamp_y = -LAMP[0] * math.sin(turn) + LAMP[1] * math.cos(turn)
    gain = 127 * spec["relief"] * strength
    relief = maps["normal"].crop(box).convert("L", matrix=(gain * lamp_x / 127.5, gain * lamp_y / 127.5, gain * LAMP[2] / 127.5,
                                                            128 - gain * (lamp_x + lamp_y + 2 * LAMP[2])))
    hollows = around_grey(high_pass(maps["depth"].crop(box), 16), spec["hollows"] * strength)
    flecks = high_pass(maps["colour"].crop(box), 24)
    flecks = around_grey(Image.blend(flecks.convert("L").convert("RGB"), flecks, spec["fleck_colour"]), spec["flecks"] * strength)
    shade = ImageChops.add(relief, hollows, scale=1, offset=-128).convert("RGB")
    out = ImageChops.add(shade, flecks, scale=1, offset=-128)
    if angle:
        out = out.rotate(angle, resample=Image.BICUBIC)
    edge = (big - side) // 2
    out = seamless(out.crop((edge, edge, edge + side, edge + side)), tile, spec["seam"])
    middle = ImageStat.Stat(out.convert("L")).median[0]
    return ImageChops.offset(out, 0, 0).point(lambda v: max(0, min(255, v + 128 - middle)))   # flat paper is exactly mid-grey


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    source, strength = Path(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in SETS.items():
        stem = source / spec["folder"] / spec["folder"]
        maps = {"normal": Image.open(f"{stem}_NormalGL.{spec['ending']}").convert("RGB"),
                "depth": Image.open(f"{stem}_Displacement.{spec['ending']}").convert("L"),
                "colour": Image.open(f"{stem}_Color.{spec['ending']}").convert("RGB")}
        for file, tile, angle, centre in spec["tiles"]:
            result = bake(maps, spec, tile, angle, centre, strength)
            path = OUT / f"{file}.webp"
            result.save(path, "WEBP", quality=76, method=6)
            stat = ImageStat.Stat(result.convert("L"))
            print(f"{path.name}: {tile} px, turned {angle:+} deg, {path.stat().st_size // 1024} KB, grey {stat.mean[0]:.1f} +- {stat.stddev[0]:.1f}")
