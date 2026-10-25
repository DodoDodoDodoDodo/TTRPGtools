<script>
  // One 5etools string with {@tag ...} markup. Spells, items, feats and options open the side pane.
  import Tagged from "./Tagged.svelte";
  import { show } from "./pane.svelte.js";
  import { spellByRef, itemByRef, content } from "./content.svelte.js";

  let { text = "" } = $props();

  const LINKS = { spell: "spell", item: "item", feat: "feat", optfeature: "optionalfeature", condition: "condition" };

  function tokens(s) {
    const out = [];
    let i = 0;
    while (i < s.length) {
      const start = s.indexOf("{@", i);
      if (start < 0) {
        out.push({ text: s.slice(i) });
        break;
      }
      if (start > i) out.push({ text: s.slice(i, start) });
      let depth = 0, j = start;
      for (; j < s.length; j++) {
        if (s[j] === "{") depth++;
        else if (s[j] === "}" && --depth === 0) break;
      }
      const inner = s.slice(start + 2, j);
      const space = inner.indexOf(" ");
      const tag = space < 0 ? inner : inner.slice(0, space);
      const body = space < 0 ? "" : inner.slice(space + 1);
      out.push({ tag, body, parts: body.split("|") });
      i = j + 1;
    }
    return out;
  }

  function display(t) {
    if (["dice", "damage", "d20", "hit", "chance", "recharge"].includes(t.tag)) return t.tag === "recharge" ? `(Recharge ${t.parts[0] || 6})` : t.parts[0];
    if (["scaledice", "scaledamage"].includes(t.tag)) return t.parts[2] || t.parts[0];
    // {@book chapter 10|PHB|10}: the third part is a chapter index, not display text
    if (["filter", "book", "adventure", "quickref"].includes(t.tag)) return t.parts[0];
    if (t.tag === "dc") return `DC ${t.parts[0]}`;
    return t.parts[2] || t.parts[0];
  }

  function open(t) {
    const kind = LINKS[t.tag];
    const ref = `${t.parts[0]}${t.parts[1] ? "|" + t.parts[1] : ""}`;
    if (kind === "spell") {
      const s = spellByRef(ref);
      if (s) show("spell", s.id);
    } else if (kind === "item") {
      const it = itemByRef(ref);
      if (it) show("item", it.id);
    } else if (kind === "feat") {
      const f = content.feats.find((x) => x.name.toLowerCase() === t.parts[0].toLowerCase());
      if (f) show("feat", f.id);
    } else if (kind === "optionalfeature") {
      const o = content.optionalfeatures.find((x) => x.name.toLowerCase() === t.parts[0].toLowerCase());
      if (o) show("optionalfeature", o.id);
    } else if (kind === "condition") {
      show("condition", t.parts[0]);
    }
  }
</script>

{#each tokens(String(text)) as t}
  {#if t.text !== undefined}{t.text}{:else if t.tag === "b" || t.tag === "bold"}<strong><Tagged text={t.body} /></strong>{:else if t.tag === "i" || t.tag === "italic"}<em><Tagged text={t.body} /></em>{:else if t.tag === "u" || t.tag === "underline"}<u><Tagged text={t.body} /></u>{:else if t.tag === "s" || t.tag === "strike"}<s><Tagged text={t.body} /></s>{:else if t.tag === "note"}<em class="note"><Tagged text={t.body} /></em>{:else if t.tag === "sup"}<sup>{t.body}</sup>{:else if t.tag === "sub"}<sub>{t.body}</sub>{:else if t.tag === "code"}<code>{t.body}</code>{:else if LINKS[t.tag]}<button type="button" class="ref ref-{t.tag}" onclick={() => open(t)}>{display(t)}</button>{:else if ["dice", "damage", "d20", "hit", "scaledice", "scaledamage"].includes(t.tag)}<span class="dice">{display(t)}</span>{:else}<span class="tag-{t.tag}">{display(t)}</span>{/if}
{/each}
