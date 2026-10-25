<script>
  import { noncanon, setNoncanon } from "./noncanon.svelte.js";
</script>
<label class="noncanon-toggle" title="Firearms, explosives and Renaissance, modern or futuristic gear (DMG chapter 9)">
  <input type="checkbox" checked={noncanon.show} onchange={(e) => setNoncanon(e.target.checked)} /> Show noncanon
</label>
