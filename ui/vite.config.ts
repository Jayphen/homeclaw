import path from "path";
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  resolve: {
    alias: {
      $lib: path.resolve(__dirname, "src/lib"),
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  // @arrow-js/sandbox ships raw TS + a QuickJS WASM asset. Excluding it from
  // dev pre-bundling lets Vite serve the WASM correctly; the production build
  // bundles it normally and lazy-splits it onto the /apps route.
  optimizeDeps: {
    exclude: ["@arrow-js/sandbox"],
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8081",
    },
  },
});
