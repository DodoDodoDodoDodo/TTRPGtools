// DDB's sheet frames and icons (extract_frames.py), fetched once per theme colour.
export const ddb = $state({ frames: {}, icons: {}, sidebar: null, theme: null });

export async function loadFrames(theme) {
  if (ddb.theme === theme) return;
  ddb.theme = theme;
  const response = await fetch(`${window.DND5E.ddb}/frames.json?theme=${encodeURIComponent(theme)}`);
  if (!response.ok) return;
  const data = await response.json();
  ddb.frames = data.frames;
  ddb.icons = data.icons;
  ddb.sidebar = data.sidebar || null;
}

// DDB's character-app stylesheet and theme variables, only while a DDB-styled view is on screen
// (they style bare elements too). Used by the sheet and the builder.
export function useSheetStyles() {
  return useStyles(["site.css", "tooltip.css", "character-app.css", "vars.css"]);
}

// Any of the /ddb/*.css stylesheets for as long as the calling view is on screen.
export function useStyles(files) {
  const links = files.map((file) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `${window.DND5E.ddb}/${file}`;
    document.head.appendChild(link);
    return link;
  });
  return () => links.forEach((link) => link.remove());
}
