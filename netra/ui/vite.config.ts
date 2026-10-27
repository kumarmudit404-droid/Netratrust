import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import { VitePWA } from "vite-plugin-pwa"
import { fileURLToPath, URL } from "node:url"

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "NetraTrust",
        short_name: "NetraTrust",
        description:
          "Offline-first diabetic-retinopathy screening. Fundus images never leave the device.",
        theme_color: "#111827",
        background_color: "#FFFFFF",
        display: "standalone",
        start_url: "/",
        // Scalable placeholder so the manifest never points at a missing file.
        // Raster 192/512 PNG icons: TBD - verify with design before shipping.
        icons: [
          {
            src: "favicon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any",
          },
        ],
      },
      workbox: {
        // Cache the app shell so a camp device keeps working with no network.
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        // NEVER cache clinical API traffic: a stale verdict or ledger state is
        // worse than no answer. Writes queue in the app, not in the SW cache.
        navigateFallbackDenylist: [/^\/v1\//],
      },
    }),
  ],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    // Local dev talks to the API on :8000. CORS on the API is a Lane A task.
    proxy: {
      "/v1": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
})
