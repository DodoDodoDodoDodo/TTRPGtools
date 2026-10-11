Textures for the DCC pages. All of them are grey (flecks faintly tinted) and lie over the flat palette colors.

1. Print grain (static/dcc_grain.svg): multiplied over the land color only, fixed to the window. In static/dcc.css, :root:
     --texture, --texture-size, --texture-strength (0 = invisible, 1 = full)

2. Paper, blended "hard-light": mid-grey leaves a color exactly as it is; the relief darkens and lightens around it.
     sheet.webp             the land color: one sheet under everything          (set Paper002)
     sheet-1 ... -6.webp    one piece per panel and the masthead                 (set Paper002)
     card-1 ... -4.webp     one piece per darker field lying on a panel          (set Paper001)
   Pieces are cut from different parts of the maps and turned by different small angles; static/dcc_assist.js
   ("layPaper") deals them out, so fields look like cut-out pieces of paper laid on one another.
   Baked from the material sets (normal, displacement and colour maps), all at once:
     python3 scripts/dcc_texture.py <folder holding Paper002_4K-JPG and Paper001_4K-PNG> [strength]
   Cuts, angles and how strongly relief, hollows and flecks show: SETS in that script.
   The block "Paper" in static/dcc.css switches it all on.
   After baking new tiles, give them new file names: Cloudflare keeps serving an old file under the same name.
