<script>
  import { ddb } from "../../lib/ddb.svelte.js";
  let { name } = $props();
</script>

<div class="ddbc-box-background">{@html ddb.frames[name] || ""}</div>
