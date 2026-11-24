import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

const backend = "http://127.0.0.1:5000"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    // During `npm run dev`, forward API, video and face-photo requests to Flask
    proxy: {
      "/api": backend,
      "/video_feed": backend,
      "/static": backend,
    },
  },
})
