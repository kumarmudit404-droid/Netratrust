import { clsx, type ClassValue } from "clsx"
import { extendTailwindMerge } from "tailwind-merge"

/**
 * Our five type-scale steps live in `tailwind.config.ts` under `fontSize`, so
 * they are NOT in tailwind-merge's default t-shirt scale. Without this, merge
 * reads `text-subhead` / `text-caption` as a text COLOUR (its colour validator
 * matches anything) and puts it in the same conflict group as `text-bg` or
 * `text-abstain` — the later class silently wins and the other is dropped.
 *
 * That is how a primary button shipped as #111827 text on a #111827 fill.
 * Declaring the scale here puts sizes and colours back in separate groups.
 * Keep this list in sync with `theme.extend.fontSize`.
 */
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [{ text: ["display", "section", "subhead", "body", "caption"] }],
    },
  },
})

/** shadcn/ui class merge helper. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
