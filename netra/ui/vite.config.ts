// vitest/config re-exports vite's defineConfig with the `test` block typed.
import { defineConfig } from "vitest/config"
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
  test: {
    // Node environment: no DOM library is in Lane B's stack, so these are
    // logic and import-time tests only.
    environment: "node",
    include: ["src/**/*.test.ts"],
    // Tests exercise the REAL client path with `fetch` stubbed, not the mock
    // responder. Without this the client's USE_MOCK branch short-circuits
    // every call and a header assertion can never fail.
    env: { VITE_USE_MOCK: "0" },
    // The default 5000ms is a COLD-CACHE trap, not a generous budget.
    // `routes.smoke.test.ts` dynamically imports Sites, which pulls in
    // Recharts; transforming that graph for the first time takes ~7s on this
    // machine and ~1s once Vite's cache is warm. With the default the suite
    // therefore passes locally and fails on a fresh clone or in CI, which is
    // the worst possible failure mode for a pre-commit gate. Raised so the
    // result depends on the code and not on whether node_modules/.vite exists.
    testTimeout: 30_000,
  },
  server: {
    port: 5173,
    // Local dev talks to the API on :8000. CORS on the API is a Lane A task.
    proxy: {
      "/v1": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
})
