import { mount } from "svelte";
import App from "./App.svelte";
import "./styles.css";

// Fonts are DDB's own, served from the private content folder, so their URLs are only known at runtime.
// Roboto and Roboto Condensed come from DDB's stylesheets (one regular condensed face, bold synthesised).
const ddb = window.DND5E.ddb;
const faces = [
  ["Mrs Eaves", "MrsEavesOT-Roman.otf", 400, "normal"],
  ["Mrs Eaves", "MrsEavesOT-Bold.otf", 700, "normal"],
  ["Mrs Eaves Small Caps", "MrsEavesSmallCapsOT.otf", 400, "normal"],
  ["Bookinsanity", "phb/Bookinsanity.woff2", 400, "normal"],
  ["Bookinsanity", "phb/Bookinsanity Bold.woff2", 700, "normal"],
  ["Bookinsanity", "phb/Bookinsanity Italic.woff2", 400, "italic"],
  ["Scaly Sans", "phb/Scaly Sans.woff2", 400, "normal"],
  ["Scaly Sans", "phb/Scaly Sans Bold.woff2", 700, "normal"],
  ["Mr Eaves SC", "phb/Mr Eaves Small Caps.woff2", 400, "normal"],
  ["Nodesto Caps", "phb/Nodesto Caps Condensed.woff2", 400, "normal"],
];
const style = document.createElement("style");
style.textContent = faces
  .map(([family, file, weight, fstyle]) =>
    `@font-face{font-family:"${family}";src:url("${ddb}/fonts/${file}");font-weight:${weight};font-style:${fstyle};font-display:swap}`)
  .join("\n");
document.head.appendChild(style);
document.documentElement.style.setProperty("--parchment", `url("${ddb}/fonts/phb/parchmentBackground.jpg")`);
document.documentElement.style.setProperty(
  "--texture",
  `url("${ddb}/assets/media.dndbeyond.com/character-app/static/media/background_texture.9efbaca70f36e40effd0.png")`,
);

const target = document.getElementById("app");
target.textContent = "";
mount(App, { target });
