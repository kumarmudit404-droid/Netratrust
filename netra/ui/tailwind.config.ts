import type { Config } from "tailwindcss"

// Tokens come from design.md section 2. Declared as CSS custom properties in
// src/index.css and referenced here, so a token change propagates everywhere.
// Never hard-code a hex in a component.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        text: { DEFAULT: "var(--text)", muted: "var(--text-muted)" },
        accent: "var(--accent)",
        usable: "var(--usable)",
        borderline: "var(--borderline)",
        reject: "var(--reject)",
        abstain: "var(--abstain)",
        "border-subtle": "var(--border-subtle)",
      },
      fontSize: {
        display: ["30px", { lineHeight: "1.2", fontWeight: "700" }],
        section: ["24px", { lineHeight: "1.25", fontWeight: "600" }],
        subhead: ["20px", { lineHeight: "1.3", fontWeight: "600" }],
        body: ["16px", { lineHeight: "1.5" }],
        caption: ["13px", { lineHeight: "1.45" }],
      },
      fontFamily: {
        sans: ["-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        // The landing's display serif (src/index.css --font-display), exposed
        // as a utility for the one spot (TopNav's wordmark) that isn't h1/h2.
        serif: ["var(--font-display)"],
      },
    },
  },
  plugins: [],
} satisfies Config
