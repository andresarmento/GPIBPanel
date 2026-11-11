import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  server: {
    port: 5173,
    // Em desenvolvimento, /api vai para o backend FastAPI
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
