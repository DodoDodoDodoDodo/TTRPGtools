import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// Fixed file names; the Flask template appends ?v=<mtime> so Cloudflare never serves a stale build.
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: "../../ttrpgtools/web/static/dnd5e/builder",
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: "src/main.js",
      output: {
        entryFileNames: "builder.js",
        chunkFileNames: "builder-[name].js",
        assetFileNames: (info) => (info.names?.[0]?.endsWith(".css") ? "builder.css" : "[name][extname]"),
      },
    },
  },
});
