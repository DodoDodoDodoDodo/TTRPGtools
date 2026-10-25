<script>
  // DDB's custom dropdown: a combobox button and a fixed-position option list placed under it.
  // Options with a `group` are listed under DDB's group labels ("5e Core Rules", "5e Expanded Rules").
  import { ddb } from "../lib/ddb.svelte.js";

  let { options = [], value = "", placeholder = "- Choose -", onchange, extraClass = "", highlight = false,
    searchable = null, width = null, optionsClass = "" } = $props();
  let open = $state(false);
  let root = $state(null);
  let pos = $state("");
  let query = $state("");
  const name = `ddb-select-${Math.random().toString(36).slice(2, 9)}`;

  const current = $derived(options.find((o) => String(o.value) === String(value)));
  const withSearch = $derived(searchable ?? options.length > 10);
  const shown = $derived(query ? options.filter((o) => o.label.toLowerCase().includes(query.toLowerCase())) : options);
  const groups = $derived.by(() => {
    const out = [];
    for (const o of shown) {
      const last = out[out.length - 1];
      if (last && last.label === (o.group || null)) last.options.push(o);
      else out.push({ label: o.group || null, options: [o] });
    }
    return out;
  });

  // DDB's list is position: fixed at --options-top (viewport px): measured on open and again on every scroll,
  // and placed above the button when the space below is short.
  function place() {
    if (!root) return;
    const r = root.getBoundingClientRect();
    const height = 300;
    const top = window.innerHeight - r.bottom < Math.min(height, 200) ? Math.max(8, r.top - height) : r.bottom;
    pos = `--options-width:${r.width}px; --options-top:${top}px; --options-height:${height}px;`;
  }
  function toggle() {
    if (!open) place();
    open = !open;
    query = "";
  }
  function pick(v) {
    open = false;
    if (String(v) !== String(value)) onchange?.(v);
  }
  function outside(event) {
    if (open && root && !root.contains(event.target)) open = false;
  }
</script>

<svelte:window onmousedown={outside} onscroll={() => open && place()} onresize={() => open && place()} />

{#snippet option(o, index)}
  {@const selected = String(o.value) === String(value ?? "")}
  <label class="styles_option__hdbrC {selected ? 'styles_focused__SQWSv' : ''}" class:ddb-option-disabled={o.disabled} aria-selected={selected} data-index={index}>
    {@html ddb.icons["select-check"] || ""}<input type="radio" {name} value={o.value} disabled={o.disabled} checked={selected} onchange={() => pick(o.value)} />{o.label}
  </label>
{/snippet}

<div class="styles_select__Rt57g {extraClass} {highlight && !current ? 'styles_highlighted__kvnld' : ''}" bind:this={root} style="{width ? `--options-width:${width};` : ''}{pos}">
  <button type="button" class="styles_button__HzQnT" role="combobox" aria-haspopup="listbox" aria-expanded={open} onclick={toggle}>
    <span class="styles_buttonText__+kIce">{current ? current.label : placeholder}</span>
    {@html ddb.icons["select-chevron"] || "▾"}
  </button>
  <div class="styles_options__XLtnf {optionsClass}" role="group">
    {#if withSearch}<input placeholder="Search..." type="search" bind:value={query} />{/if}
    <div class="styles_optionList__u567h" role="menu">
      {#if placeholder}{@render option({ value: "", label: placeholder }, 0)}{/if}
      {#each groups as g, gi}
        {#if g.label}
          <div class="styles_optionGroup__mGNUL">
            <label class="styles_groupLabel__S6Fic">{g.label}</label>
            {#each g.options as o (o.value)}{@render option(o, options.indexOf(o) + 1)}{/each}
          </div>
        {:else}
          {#each g.options as o (o.value)}{@render option(o, options.indexOf(o) + 1)}{/each}
        {/if}
      {/each}
    </div>
  </div>
</div>
