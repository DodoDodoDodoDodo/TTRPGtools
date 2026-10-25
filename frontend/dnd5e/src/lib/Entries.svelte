<script>
  // 5etools entry tree: strings, named sections, lists, tables, insets, quotes, spell DC boxes.
  // `ddb` renders DDB's compendium markup instead: flat paragraphs and h5 headings, the first
  // paragraph marked compendium-hr, tables under a Table-Title heading.
  import Entries from "./Entries.svelte";
  import Tagged from "./Tagged.svelte";
  import { ABILITY_NAMES } from "./format.js";

  let { entries = [], depth = 0, ddb = false } = $props();
  const list = $derived(Array.isArray(entries) ? entries : [entries]);

  const abilityList = (attrs) => (attrs || []).map((a) => ABILITY_NAMES[a] || a).join(" or ");
</script>

{#each list as e}
  {#if ddb && typeof e === "string"}
    <p class={depth === 0 && e === list[0] ? "compendium-hr" : ["abilityDc", "abilityAttackMod"].includes(list[list.indexOf(e) + 1]?.type) ? "Core-Styles_Core-Body-Last--to-apply-extra-space-" : "Core-Styles_Core-Body"}><Tagged text={e} /></p>
  {:else if ddb && e?.type === "table"}
    {#if e.caption}<h5 class="Table-Styles_Table-Title"><Tagged text={e.caption} /></h5>{/if}
    <table class="compendium-left-aligned-table">
      {#if e.colLabels}<thead><tr>{#each e.colLabels as c}<th><Tagged text={c} /></th>{/each}</tr></thead>{/if}
      <tbody>{#each e.rows || [] as row}<tr>{#each (Array.isArray(row) ? row : row.row || []) as cell}<td>{#if typeof cell === "string" || typeof cell === "number"}<Tagged text={String(cell)} />{:else}<Entries entries={[cell]} depth={depth + 1} ddb />{/if}</td>{/each}</tr>{/each}</tbody>
    </table>
  {:else if ddb && (e?.type === "abilityDc" || e?.type === "abilityAttackMod")}
    <p class="List-Styles_List-Item-Centered"><strong><span class="Sans-Serif-Character-Styles_Bold-Sans-Serif">{e.name} {e.type === "abilityDc" ? "save DC" : "attack modifier"} </span></strong>= {e.type === "abilityDc" ? "8 + " : ""}your proficiency bonus + your {abilityList(e.attributes)} modifier</p>
  {:else if ddb && e && typeof e === "object" && (e.type === "entries" || e.type === "section" || (!e.type && e.entries)) }
    {#if e.name}<h5 class="compendium-hr"><Tagged text={e.name} /></h5>{/if}
    {#if e.entries}<Entries entries={e.entries} depth={depth + 1} ddb />{/if}
  {:else if typeof e === "string"}
    <p><Tagged text={e} /></p>
  {:else if e && typeof e === "object"}
    {#if e.type === "list"}
      <ul class="entries-list" class:no-bullets={e.style === "list-hang-notitle" || e.style === "list-no-bullets"}>
        {#each e.items || [] as item}
          <li>
            {#if typeof item === "string"}
              <Tagged text={item} />
            {:else if item.type === "item" || item.type === "itemSub"}
              <strong><Tagged text={item.name} /></strong>
              {#if item.entry}<Tagged text={item.entry} />{/if}
              {#if item.entries}<Entries entries={item.entries} depth={depth + 1} {ddb} />{/if}
            {:else}
              <Entries entries={[item]} depth={depth + 1} {ddb} />
            {/if}
          </li>
        {/each}
      </ul>
    {:else if e.type === "table"}
      <div class="table-wrap">
        <table class="entries-table">
          {#if e.caption}<caption><Tagged text={e.caption} /></caption>{/if}
          {#if e.colLabels}<thead><tr>{#each e.colLabels as c}<th><Tagged text={c} /></th>{/each}</tr></thead>{/if}
          <tbody>
            {#each e.rows || [] as row}
              <tr>
                {#each (Array.isArray(row) ? row : row.row || []) as cell}
                  <td>
                    {#if typeof cell === "string" || typeof cell === "number"}<Tagged text={String(cell)} />
                    {:else if cell?.roll}{cell.roll.exact ?? `${cell.roll.min}–${cell.roll.max}`}
                    {:else}<Entries entries={[cell]} depth={depth + 1} />{/if}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else if e.type === "abilityDc"}
      <p class="formula"><strong>{e.name} save DC</strong> = 8 + your proficiency bonus + your {abilityList(e.attributes)} modifier</p>
    {:else if e.type === "abilityAttackMod"}
      <p class="formula"><strong>{e.name} attack modifier</strong> = your proficiency bonus + your {abilityList(e.attributes)} modifier</p>
    {:else if e.type === "quote"}
      <blockquote><Entries entries={e.entries} depth={depth + 1} />{#if e.by}<footer>— <Tagged text={e.by} /></footer>{/if}</blockquote>
    {:else if e.type === "inset" || e.type === "insetReadaloud" || e.type === "variant" || e.type === "variantInner" || e.type === "variantSub"}
      <aside class="inset">{#if e.name}<h5><Tagged text={e.name} /></h5>{/if}<Entries entries={e.entries} depth={depth + 1} {ddb} /></aside>
    {:else if e.type === "inline" || e.type === "inlineBlock"}
      <p>{#each e.entries || [] as part}{#if typeof part === "string"}<Tagged text={part} />{:else}<Entries entries={[part]} depth={depth + 1} />{/if}{/each}</p>
    {:else if e.type === "refOptionalfeature"}
      <p><Tagged text={`{@optfeature ${e.optionalfeature}}`} /></p>
    {:else if e.type === "options"}
      <Entries entries={e.entries} depth={depth} {ddb} />
    {:else if e.type === "image" || e.type === "gallery" || e.type === "statblock" || e.type === "hr"}
      <!-- not shown -->
    {:else if e.entries || e.name}
      <section class="entries-section depth-{Math.min(depth, 3)}">
        {#if e.name}<h5 class="entry-name"><Tagged text={e.name} /></h5>{/if}
        {#if e.entries}<Entries entries={e.entries} depth={depth + 1} />{/if}
      </section>
    {:else if e.entry}
      <p><Tagged text={e.entry} /></p>
    {/if}
  {/if}
{/each}
