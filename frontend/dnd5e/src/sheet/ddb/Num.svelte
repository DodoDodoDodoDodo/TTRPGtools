<script>
  // DDB's number display: signed modifiers ("+3") or a value with a unit ("30 ft.").
  let { value = 0, large = false, unit = null } = $props();
  const n = $derived(Number(value) || 0);
</script>

{#if unit}
  <span class="styles_numberDisplay__Rg1za {large ? 'styles_largeDistance__YVw96 styles_large__3C8uq' : ''}"><span>{n}</span><span class="styles_label__L8mZK {large ? 'styles_largeLabel__E3v8Y' : ''} styles_labelSignColor__Klmbs">{unit}</span></span>
{:else}
  <span class="styles_numberDisplay__Rg1za styles_signed__scf97 {large ? 'styles_large__3C8uq' : ''}"><span class="styles_sign__NdR6X {large ? 'styles_largeSign__V9-jS' : ''} styles_labelSignColor__Klmbs" aria-label={n < 0 ? "minus" : "plus"}>{n < 0 ? "-" : "+"}</span><span>{Math.abs(n)}</span></span>
{/if}
