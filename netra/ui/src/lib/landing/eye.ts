/**
 * The scroll-driven 3D eye, ported from the inline `<script>` in
 * `netra/ui/landing-source.html`.
 *
 * The geometry, the structure table, the slot positions, the timeline windows,
 * the dust field and every easing string below are that file's, unchanged -
 * this is a port, not a redesign. Four things had to change to make it a
 * React route:
 *
 *  1. It was an IIFE that ran until the tab closed. It is now
 *     `mountEye(root) -> destroy()`.
 *  2. Lookups are scoped to `root`. The source owned the document; here
 *     /capture, /grade, /sites, /ledger and /referrals share it, and React
 *     StrictMode mounts the route twice in development.
 *  3. Anime.js selector-string targets (`.lb`, `.sl`, `#track`, the lid and
 *     crease paths) are resolved against `root`, for the same reason.
 *  4. Every listener, timer, RAF and timeline is tracked so `destroy()` can
 *     undo it. Without that, navigating to /capture leaves a scroll observer,
 *     a pointer RAF and two setTimeout chains running for the rest of the
 *     session - on a device that may well be a phone in a field camp.
 */

import anime, { type AnimeTarget, type AnimeTimeline } from "@/vendor/anime"

interface Slice {
  z: number
  svg: string
  cls?: string
}

interface Part {
  id: string
  struct: string
  box: number[]
  slices: Slice[]
  gk?: number
  origin?: string
  bloom?: Record<string, number>
  el?: HTMLElement
}

interface Slot {
  x: number
  y: number
  z: number
  rx: number
  ry: number
  rz: number
  s: number
}

/** One row of the source's structure table, exactly as written there. */
interface StructSeed {
  key: string
  name: string
  ctr: number[]
  slot: Slot
}

/** A seed plus the fields the DOM and timeline builds fill in. */
interface Struct extends StructSeed {
  win: [number, number]
  el: HTMLElement
  members: Part[]
  multi: boolean
}

interface Dust {
  x: number
  y: number
  z: number
  vx: number
  vy: number
  vz: number
  travel: number
  size: number
  phase: number
  spin: number
  tone: number
}

/**
 * Build the eye inside `root` and start it.
 *
 * `root` must already hold the landing markup (`#rig`, `#track`, `#labels`,
 * `#hud`, `#cue`, `#disintegration`). Returns the teardown.
 */
export function mountEye(root: HTMLElement): () => void {
  // --- teardown bookkeeping, which everything below registers with -------
  const listeners: Array<() => void> = []
  let pointerRaf: number | null = null

  function on(
    target: Window | Document | HTMLElement,
    type: string,
    handler: EventListenerOrEventListenerObject,
    opts?: AddEventListenerOptions,
  ): void {
    target.addEventListener(type, handler, opts)
    listeners.push(() => target.removeEventListener(type, handler, opts))
  }

  const { animate, createTimeline, onScroll, stagger, utils, svg } = anime;
  // Scoped to `root`, not the document: /capture and the other four routes
  // share this document, and React StrictMode mounts the route twice in dev.
  const $ = <T extends Element = HTMLElement>(s: string): T =>
    root.querySelector(s) as unknown as T;
  const $$ = (s: string): Element[] => [...root.querySelectorAll(s)];
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v));
  let seed = 7;
  const rnd = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; };
  const fx = (n: number) => n.toFixed(1);
  const rad = (a: number) => a * Math.PI / 180;

  const rig = $('#rig'), sway = $('#sway'), glow = $('#glow'), floor = $('#floor');
  const A = 'M64 212Q300 92 536 212Q300 332 64 212Z';                                   // the eye opening
  const LIDU = 'M26 216C70 146 150 52 300 46C450 52 530 146 574 216L536 212Q300 92 64 212Z'; // upper lid shell
  const LIDL = 'M26 216C70 270 150 340 300 346C450 340 530 270 574 216L536 212Q300 332 64 212Z'; // lower lid shell
  const circ = (r: number, a: string) => `<circle cx="300" cy="210" r="${r}" ${a}/>`;

  /* ------------------------------------------------------------------
     1. THE PIECES (the model). Every piece is a stack of slices at
        different depths (z), so it has real thickness. `struct` says
        which anatomical structure the piece belongs to.
  ------------------------------------------------------------------ */
  const parts: Part[] = [];
  const add = (p: Part) => { parts.push(p); };

  // eyelashes: grow out of the lid edge, fan toward the corners
  function lashes(
    upper: boolean, count: number, minLen: number, maxLen: number, w: number,
  ) {
    let out = '';
    for (let i = 0; i < count; i++) {
      const t = 0.07 + 0.86 * (i / (count - 1));
      const x = 64 + 472 * t, e = 240 * t * (1 - t);
      const y = upper ? 212 - e : 212 + e;
      let tx = 472, ty = (upper ? -1 : 1) * 240 * (1 - 2 * t);
      const tn = Math.hypot(tx, ty); tx /= tn; ty /= tn;
      let nx = upper ? ty : -ty, ny = upper ? -tx : tx;           // outward normal
      nx += (t - 0.5) * 0.9;                                        // lean toward the corners
      const nn = Math.hypot(nx, ny); nx /= nn; ny /= nn;
      const len = (minLen + rnd() * (maxLen - minLen)) * (0.55 + 0.45 * Math.sin(Math.PI * t));
      const rx = x - nx * 1.5, ry = y - ny * 1.5, curl = (t - 0.5) * len * 0.3;
      out += `<path d="M${fx(rx)} ${fx(ry)}Q${fx(rx + nx * len * .5 + curl * .6)} ${fx(ry + ny * len * .5)} ${fx(rx + nx * len + curl)} ${fx(ry + ny * len)}" fill="none" stroke="#2b1b15" stroke-width="${w}" stroke-linecap="round"/>`;
    }
    return `<g class="lb">${out}</g>`;
  }

  // skin-coloured lids: thick shells; the inner fill closes over the eye to blink
  add({ id: 'lid-up', struct: 'lid-up', box: [18, 40, 564, 195],
        slices: [
          { z: 66, svg: `<path d="${LIDU}" fill="#38291b"/>` },
          { z: 72, svg: `<path d="${LIDU}" fill="#70512b"/>` },
          { z: 78, cls: 'keep', svg:
            `<defs><clipPath id="ap-u"><path d="${A}"/></clipPath><clipPath id="cl-u"><path d="${LIDU}"/></clipPath></defs>
             <path d="${LIDU}" fill="url(#g-lidU)"/>
             <g clip-path="url(#cl-u)"><path d="M205 82 Q295 48 385 94 L365 114 Q286 79 218 107Z" fill="#ffe8d4" opacity=".18"/><path d="M99 171 Q300 5 505 176" fill="none" stroke="#e7cb81" stroke-width="2.5" opacity=".8"/><circle cx="125" cy="158" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M122.5 158h5" stroke="#251b13" stroke-width="1.4"/><circle cx="190" cy="120" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M187.5 120h5" stroke="#251b13" stroke-width="1.4"/><circle cx="265" cy="100" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M262.5 100h5" stroke="#251b13" stroke-width="1.4"/><circle cx="340" cy="102" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M337.5 102h5" stroke="#251b13" stroke-width="1.4"/><circle cx="415" cy="125" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M412.5 125h5" stroke="#251b13" stroke-width="1.4"/><circle cx="480" cy="165" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M477.5 165h5" stroke="#251b13" stroke-width="1.4"/>
               <ellipse cx="205" cy="102" rx="112" ry="26" transform="rotate(-18 205 102)" fill="url(#g-spec)" opacity=".55"/>
               <ellipse cx="428" cy="104" rx="62" ry="11" transform="rotate(14 428 104)" fill="url(#g-spec)" opacity=".4"/>
             </g>
             <g clip-path="url(#ap-u)"><path id="lidfill-up" class="p" d="M40 120H560V212Q300 220 40 212Z" fill="url(#g-fillU)"/></g>
             <path id="arc-up" d="M64 212Q300 92 536 212" fill="none" stroke="#49321b" stroke-opacity=".9" stroke-width="3" stroke-linecap="round"/>
             <path id="crease-up" d="M96 178C124 122 196 80 292 72" fill="none" stroke="#ffe5a2" stroke-opacity=".55" stroke-width="5" stroke-linecap="round"/>` }
        ] });
  add({ id: 'lid-low', struct: 'lid-low', box: [18, 200, 564, 160],
        slices: [
          { z: 64, svg: `<path d="${LIDL}" fill="#442a1b"/>` },
          { z: 70, svg: `<path d="${LIDL}" fill="#88572e"/>` },
          { z: 76, cls: 'keep', svg:
            `<defs><clipPath id="ap-l"><path d="${A}"/></clipPath><clipPath id="cl-l"><path d="${LIDL}"/></clipPath></defs>
             <path d="${LIDL}" fill="url(#g-lidL)"/>
             <g clip-path="url(#cl-l)"><path d="M230 326 Q300 352 370 326 L350 309 Q300 324 250 309Z" fill="#ffe8d4" opacity=".12"/><path d="M102 252 Q300 391 500 252" fill="none" stroke="#caa458" stroke-width="2.5" opacity=".85"/><circle cx="125" cy="270" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M122.5 270h5" stroke="#251b13" stroke-width="1.4"/><circle cx="190" cy="300" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M187.5 300h5" stroke="#251b13" stroke-width="1.4"/><circle cx="265" cy="319" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M262.5 319h5" stroke="#251b13" stroke-width="1.4"/><circle cx="340" cy="319" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M337.5 319h5" stroke="#251b13" stroke-width="1.4"/><circle cx="415" cy="300" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M412.5 300h5" stroke="#251b13" stroke-width="1.4"/><circle cx="480" cy="270" r="5" fill="#5d401f" stroke="#f0ce78" stroke-width="1.4"/><path d="M477.5 270h5" stroke="#251b13" stroke-width="1.4"/><ellipse cx="300" cy="326" rx="132" ry="13" fill="url(#g-spec)" opacity=".4"/></g>
             <g clip-path="url(#ap-l)"><path id="lidfill-low" class="p" d="M40 330H560V212Q300 220 40 212Z" fill="url(#g-fillL)"/></g>
             <path id="arc-low" d="M64 212Q300 332 536 212" fill="none" stroke="#49321b" stroke-opacity=".85" stroke-width="3" stroke-linecap="round"/>
             <path id="crease-low" d="M92 232Q300 342 508 232" fill="none" stroke="#ffe5a2" stroke-opacity=".45" stroke-width="3.5" stroke-linecap="round"/>` }
        ] });

  // lashes
  add({ id: 'lash-up', struct: 'lash-up', box: [30, 100, 540, 125], slices: [{ z: 80, svg: lashes(true, 22, 20, 34, 2.8) }] });
  add({ id: 'lash-low', struct: 'lash-low', box: [30, 205, 540, 95], slices: [{ z: 78, svg: lashes(false, 14, 9, 17, 2.2) }] });

  // glass dome and sparkle
  add({ id: 'highlight', struct: 'highlight', gk: 0.8, box: [240, 150, 130, 120], slices: [{ z: 66, svg:
    `<ellipse cx="266" cy="178" rx="20" ry="9" fill="#fff" fill-opacity=".95" transform="rotate(-24 266 178)"/><circle cx="346" cy="248" r="6" fill="#fff" fill-opacity=".55"/>` }] });
  add({ id: 'cornea', struct: 'cornea', gk: 0.9, box: [204, 114, 192, 192], slices: [{ z: 60, svg:
    `${circ(92, 'fill="url(#g-cornea)"')}${circ(92, 'fill="none" stroke="#fff" stroke-opacity=".2" stroke-width="1.5"')}
     <ellipse cx="300" cy="172" rx="66" ry="14" fill="#fff" fill-opacity=".2"/>
     <path d="M232 190A74 74 0 0 1 300 150" fill="none" stroke="#fff" stroke-opacity=".28" stroke-width="5" stroke-linecap="round"/>` }] });

  // iris starburst: 12 shards (they fan out slightly when this structure separates)
  for (let i = 0; i < 12; i++) {
    const a0 = i * 30 + 0.6, a1 = (i + 1) * 30 - 0.6, am = (a0 + a1) / 2, rv = 50, rt = 39, r2 = 86;
    const pt = (r: number, a: number) => `${fx(300 + r * Math.cos(rad(a)))} ${fx(210 + r * Math.sin(rad(a)))}`;
    const d = `M${pt(rv, a0)}L${pt(r2, a0)}A${r2} ${r2} 0 0 1 ${pt(r2, a1)}L${pt(rv, a1)}L${pt(rt, am)}Z`;
    let fib = '';
    for (let k = 0; k < 6; k++) {
      const a = a0 + (k + .5) * (a1 - a0) / 6, ra = 52 + rnd() * 6, rb = r2 - 3 - rnd() * 14, dark = k % 2 === 0;
      fib += `<line x1="${fx(300 + ra * Math.cos(rad(a)))}" y1="${fx(210 + ra * Math.sin(rad(a)))}" x2="${fx(300 + rb * Math.cos(rad(a)))}" y2="${fx(210 + rb * Math.sin(rad(a)))}" stroke="${dark ? '#052b42' : '#a8edff'}" stroke-opacity="${dark ? .4 : .38}" stroke-width="1.2" stroke-linecap="round"/>`;
    }
    const rc = 65, cx = 300 + rc * Math.cos(rad(am)), cy = 210 + rc * Math.sin(rad(am));
    add({ id: 'shard-' + i, struct: 'burst', gk: 1,
          box: [Math.round(cx - 32), Math.round(cy - 32), 64, 64],
          origin: `${fx(cx / 6)}% ${fx(cy / 4.2)}%`,
          bloom: { x: Math.cos(rad(am)) * 34, y: Math.sin(rad(am)) * 34, z: (rnd() - .3) * 70,
                   rotateX: (rnd() - .5) * 70, rotateY: (rnd() - .5) * 70, rotateZ: (rnd() - .5) * 40 },
          slices: [
            { z: 23.2, svg: `<path d="${d}" fill="#4e381d"/>` },
            { z: 25, svg: `<path d="${d}" fill="url(#g-iris-u)" stroke="#4a351d" stroke-opacity=".5" stroke-width=".8"/>${fib}
                           <path d="M${pt(rv, a0)}L${pt(rt, am)}L${pt(rv, a1)}" fill="none" stroke="#f6dc82" stroke-opacity=".9" stroke-width="1.7" stroke-linejoin="round"/>` }
          ] });
  }
  add({ id: 'limbal', struct: 'limbal', gk: 1, box: [210, 120, 180, 180], slices: [
          { z: 22.8, svg: circ(85, 'fill="none" stroke="#251b13" stroke-width="7"') },
          { z: 25.6, svg: circ(85, 'fill="none" stroke="#7b5b2c" stroke-opacity=".95" stroke-width="7"') } ] });
  const pupilSlices: Slice[] = [];
  for (let i = 0; i < 2; i++) pupilSlices.push({ z: 22 + i * 2.5, svg: circ(29, 'fill="#000"') });
  pupilSlices.push({ z: 27, svg: circ(29, 'fill="url(#g-pupil)" stroke="#2a3040" stroke-width="2"') });
  add({ id: 'pupil', struct: 'pupil', gk: 1.15, box: [266, 176, 68, 68], slices: pupilSlices });
  let irisFib = '';
  for (let i = 0; i < 44; i++) {
    const a = rnd() * Math.PI * 2, ra = 30 + rnd() * 3, rb = 40 + rnd() * 8, w = i % 2;
    irisFib += `<line x1="${fx(300 + ra * Math.cos(a))}" y1="${fx(210 + ra * Math.sin(a))}" x2="${fx(300 + rb * Math.cos(a))}" y2="${fx(210 + rb * Math.sin(a))}" stroke="${w ? '#f3d27a' : '#5b3a12'}" stroke-opacity="${(.35 + rnd() * .3).toFixed(2)}" stroke-width="1.1" stroke-linecap="round"/>`;
  }
  for (let i = 0; i < 70; i++) {
    const a = rnd() * Math.PI * 2, ra = 48 + rnd() * 6, rb = 70 + rnd() * 15, w = i % 2;
    irisFib += `<line x1="${fx(300 + ra * Math.cos(a))}" y1="${fx(210 + ra * Math.sin(a))}" x2="${fx(300 + rb * Math.cos(a))}" y2="${fx(210 + rb * Math.sin(a))}" stroke="${w ? '#a8edff' : '#052b42'}" stroke-opacity="${(.25 + rnd() * .25).toFixed(2)}" stroke-width="1.1" stroke-linecap="round"/>`;
  }
  const irisShade = ['#071b23', '#0c2c38', '#124456', '#17637c'];
  add({ id: 'iris', struct: 'iris', gk: 1, box: [210, 120, 180, 180],
        slices: [...irisShade.map((c, i) => ({ z: 11 + i * 4, svg: circ(88, `fill="${c}"`) })),
                 { z: 24, svg: circ(88, 'fill="url(#g-iris)"') + irisFib + '<path d="M300 128v8" transform="rotate(0 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(10 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(20 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(30 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(40 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(50 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(60 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(70 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(80 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(90 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(100 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(110 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(120 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(130 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(140 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(150 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(160 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(170 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(180 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(190 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(200 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(210 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(220 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(230 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(240 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(250 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(260 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(270 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(280 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(290 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(300 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(310 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(320 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v8" transform="rotate(330 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(340 300 210)" stroke="#ffe4a0" stroke-width="1.3"/><path d="M300 128v4" transform="rotate(350 300 210)" stroke="#ffe4a0" stroke-width="1.3"/>' }] });

  // tear ducts, blood vessels, and the two halves of the white
  add({ id: 'ducts', struct: 'ducts', box: [55, 185, 490, 60], slices: [{ z: 4, svg:
    `<ellipse cx="88" cy="214" rx="30" ry="20" fill="url(#g-corner)"/><ellipse cx="512" cy="214" rx="30" ry="20" fill="url(#g-corner)"/>` }] });
  add({ id: 'veins', struct: 'veins', box: [55, 175, 490, 80], slices: [{ z: 3, svg:
    `<g fill="none" stroke="#8d653c" stroke-opacity=".5" stroke-width="1.3" stroke-linecap="round">
       <path d="M80 212C112 204 134 196 170 196"/><path d="M84 218C118 226 140 236 176 242"/><path d="M110 210C126 218 138 218 152 215"/>
       <path d="M520 212C488 204 466 196 430 196"/><path d="M516 218C482 226 460 236 424 242"/><path d="M490 210C474 218 462 218 448 215"/></g>` }] });
  ['l', 'r'].forEach((side: string) => {
    const x = side === 'l' ? 0 : 299, cid = 'cs-' + side;
    const g = (inner: string) => `<g clip-path="url(#${cid})">${inner}</g>`;
    add({ id: 'sclera-' + side, struct: 'sclera',
          box: side === 'l' ? [58, 145, 250, 135] : [292, 145, 250, 135],
          origin: side === 'l' ? '30.5% 50.5%' : '69.5% 50.5%',
          bloom: side === 'l' ? { x: -66, rotateY: -22, rotateZ: -4 } : { x: 66, rotateY: 22, rotateZ: 4 },
          slices: [
            { z: -10, svg: `<defs><clipPath id="${cid}"><rect x="${x}" y="0" width="301" height="420"/></clipPath></defs>` + g(`<path d="${A}" fill="#b49a9a"/>`) },
            { z: -5, svg: g(`<path d="${A}" fill="#d3c3c3"/>`) },
            { z: 0, svg: g(`<path d="${A}" fill="url(#g-sclera)"/><path d="${A}" fill="url(#g-shade)"/>`) }
          ] });
  });

  /* ------------------------------------------------------------------
     2. THE EXPLODED VIEW. Front to back, one structure at a time. Each
        has its own resting spot in space (slot: centre x/y in px at 1x
        relative to the eye's centre, depth z, tilt, size).
  ------------------------------------------------------------------ */
  const structSeeds: StructSeed[] = [
    { key: 'lid-up',    name: 'Upper eyelid',   ctr: [300, 137], slot: { x: -20,  y: -262, z: 150,  rx: -28, ry: 14,  rz: -4,  s: .46 } },
    { key: 'lid-low',   name: 'Lower eyelid',   ctr: [300, 280], slot: { x: 60,   y: 270,  z: 130,  rx: 26,  ry: -12, rz: 3,   s: .46 } },
    { key: 'lash-up',   name: 'Upper lashes',   ctr: [300, 162], slot: { x: 150,  y: -190, z: 190,  rx: -30, ry: -18, rz: 6,   s: .46 } },
    { key: 'lash-low',  name: 'Lower lashes',   ctr: [300, 252], slot: { x: -110, y: 205,  z: 150,  rx: 24,  ry: 16,  rz: -5,  s: .46 } },
    { key: 'highlight', name: 'Highlights',     ctr: [305, 210], slot: { x: -190, y: -170, z: 250,  rx: 0,   ry: 0,   rz: -32, s: 1.0 } },
    { key: 'cornea',    name: 'Cornea',         ctr: [300, 210], slot: { x: 205,  y: -85,  z: 210,  rx: 8,   ry: -30, rz: 0,   s: .72 } },
    { key: 'burst',     name: 'Iris starburst', ctr: [300, 210], slot: { x: -150, y: 25,   z: 120,  rx: 14,  ry: 24,  rz: 0,   s: .74 } },
    { key: 'limbal',    name: 'Limbal ring',    ctr: [300, 210], slot: { x: 210,  y: 95,   z: -100, rx: 58,  ry: 14,  rz: 0,   s: .70 } },
    { key: 'pupil',     name: 'Pupil',          ctr: [300, 210], slot: { x: -5,   y: -70,  z: 260,  rx: -14, ry: 36,  rz: 0,   s: 1.2 } },
    { key: 'iris',      name: 'Iris',           ctr: [300, 210], slot: { x: 15,   y: 70,   z: -30,  rx: 18,  ry: -28, rz: 0,   s: .80 } },
    { key: 'ducts',     name: 'Tear ducts',     ctr: [300, 215], slot: { x: 140,  y: 185,  z: 100,  rx: 12,  ry: 0,   rz: -6,  s: .55 } },
    { key: 'veins',     name: 'Blood vessels',  ctr: [300, 215], slot: { x: -80,  y: -135, z: -60,  rx: 30,  ry: 0,   rz: 0,   s: .65 } },
    { key: 'sclera',    name: 'Sclera',         ctr: [300, 212], slot: { x: 25,   y: -5,   z: -150, rx: 6,   ry: 0,   rz: 0,   s: .55 } }
  ];
  // The seed table above is the source's data, untouched. The mutable fields
  // the build steps fill in are added here rather than inline, so that table
  // stays readable as a table.
  const structs: Struct[] = structSeeds.map((s) => ({
    ...s,
    win: [0, 0] as [number, number],
    el: null as unknown as HTMLElement,
    members: [] as Part[],
    multi: false,
  }));
  const N = structs.length;
  structs.forEach((st, i) => { st.win = [Math.round(i / N * 780), Math.round(i / N * 780) + 200]; });

  /* ------------------------------------------------------------------
     3. BUILD THE DOM (one wrapper per structure, pieces inside it)
  ------------------------------------------------------------------ */
  function buildPart(p: Part, parent: HTMLElement) {
    const el = document.createElement('div');
    el.className = 'part'; el.dataset.id = p.id;
    if (p.origin) el.style.transformOrigin = p.origin;
    const fd = (4 + rnd() * 3).toFixed(2) + 's', fdl = '-' + (rnd() * 5).toFixed(2) + 's';
    p.slices.forEach(s => el.insertAdjacentHTML('beforeend',
      `<svg class="sl ${s.cls || ''}" viewBox="${p.box.join(' ')}" style="left:${p.box[0] / 6}%;top:${p.box[1] / 4.2}%;width:${p.box[2] / 6}%;height:${p.box[3] / 4.2}%;--z:${s.z};--gk:${p.gk || 0};--fd:${fd};--fdl:${fdl}">${s.svg}</svg>`));
    parent.appendChild(el); p.el = el; return el;
  }
  structs.forEach(st => {
    const members = parts.filter(p => p.struct === st.key);
    st.members = members;
    if (members.length === 1) { st.el = buildPart(members[0], rig); st.multi = false; }
    else { st.el = document.createElement('div'); st.el.className = 'part'; rig.appendChild(st.el); members.forEach(m => buildPart(m, st.el)); st.multi = true; }
    st.el.style.transformOrigin = `${fx(st.ctr[0] / 6)}% ${fx(st.ctr[1] / 4.2)}%`;
  });

  // anatomy list
  const labList = $('#lab-list');
  labList.innerHTML = structs.map((st, i) => `<div class="lab" data-i="${i}">${String(i + 1).padStart(2, '0')}&nbsp; ${st.name}</div>`).join('');
  const labRows = [...labList.querySelectorAll('.lab')];
  const labels = $('#labels');

  const hud = $('#hud'), hudState = $('#hud-state'), hudBar = $('#hud-bar');
  // Resolved rather than left as selector strings: Anime.js would otherwise
  // search the whole document, and this module is what built these ids.
  const lidFills = [$<SVGElement>('#lidfill-up'), $<SVGElement>('#lidfill-low')];
  const lashGroups = $$('.lb');
  const allSlices = $$('.sl');
  const fadeInSlices = $$('.sl:not(.keep)');
  utils.set(lidFills, { scaleY: 0 });

  /* ------------------------------------------------------------------
     3b. SCROLL-DRIVEN 3D DISINTEGRATION.
     The eye's actual SVG anatomy pieces are animated by the Anime.js
     scroll timeline. The canvas only adds a few depth particles.
  ------------------------------------------------------------------ */
  const dustCanvas = $<HTMLCanvasElement>('#disintegration');
  const dustCanvas2d = dustCanvas.getContext('2d');
  const dustCtx = dustCanvas2d as CanvasRenderingContext2D;
  const dust: Dust[] = [];
  const DUST_COUNT = 1250;
  const CAMERA = 1180;
  let dustW = 0, dustH = 0, dustDpr = 1;

  for (let i = 0; i < DUST_COUNT; i++) {
    const a = rnd() * Math.PI * 2;
    const r = Math.sqrt(rnd());
    const ex = Math.cos(a) * r;
    const ey = Math.sin(a) * r * 0.52;
    // Mostly radial motion, with a strong independent depth component.
    const radial = 0.55 + rnd() * 0.9;
    const vx = Math.cos(a) * radial + (rnd() - 0.5) * 0.85;
    const vy = Math.sin(a) * radial * 0.75 + (rnd() - 0.5) * 0.8;
    const vz = (rnd() - 0.43) * 2.2;
    dust.push({
      x: ex, y: ey, z: (rnd() - 0.5) * 22,
      vx, vy, vz,
      travel: 260 + rnd() * 620,
      size: 0.65 + rnd() * 1.9,
      phase: rnd() * Math.PI * 2,
      spin: (rnd() - 0.5) * 5,
      tone: rnd()
    });
  }

  function resizeDust() {
    const rect = dustCanvas.getBoundingClientRect();
    dustDpr = Math.min(devicePixelRatio || 1, 2);
    dustW = rect.width;
    dustH = rect.height;
    dustCanvas.width = Math.round(dustW * dustDpr);
    dustCanvas.height = Math.round(dustH * dustDpr);
    dustCtx.setTransform(dustDpr, 0, 0, dustDpr, 0, 0);
  }

  function renderDisintegration(progress: number) {
    if (!dustCanvas2d) return;
    // Dust is only a secondary accent. The actual SVG anatomy pieces are
    // animated by Anime.js below; never fade the whole rig away here.
    const start = 0.88;
    const amount = clamp((progress - start) / (1 - start), 0, 1);
    dustCtx.clearRect(0, 0, dustW, dustH);
    rig.style.opacity = '1';
    if (amount <= 0) return;

    const rect = rig.getBoundingClientRect();
    const cx = rect.left + rect.width * 0.5;
    const cy = rect.top + rect.height * 0.505;
    const rx = rect.width * 0.49;
    const ry = rect.height * 0.285;
    const eased = amount * amount * (3 - 2 * amount);
    const alphaBase = clamp(amount * 3.2, 0, 1) * (1 - amount * 0.24);

    // Draw far fragments first, then nearer fragments for a stronger depth cue.
    const ordered = dust.slice().sort((a: Dust, b: Dust) => (a.z + b.vz * b.travel * eased) - (a.z + a.vz * a.travel * eased));
    for (const d of ordered) {
      const t = eased * d.travel;
      const wx = d.x * rx + d.vx * t;
      const wy = d.y * ry + d.vy * t;
      const wz = d.z + d.vz * t;
      const perspective = CAMERA / Math.max(280, CAMERA - wz);
      const x = cx + wx * perspective;
      const y = cy + wy * perspective;
      if (x < -40 || x > dustW + 40 || y < -40 || y > dustH + 40) continue;

      const shimmer = 0.78 + 0.22 * Math.sin(d.phase + amount * 10);
      const opacity = alphaBase * shimmer;
      const size = d.size * perspective * (0.75 + eased * 0.4);
      const tailX = d.vx * 7 * perspective;
      const tailY = d.vy * 7 * perspective;
      dustCtx.globalAlpha = opacity;
      dustCtx.fillStyle = d.tone > 0.76 ? '#8fd3ff' : '#eef0f5';
      dustCtx.strokeStyle = d.tone > 0.76 ? 'rgba(143,211,255,.55)' : 'rgba(245,246,250,.42)';
      dustCtx.lineWidth = Math.max(0.45, size * 0.55);

      // A mix of tiny flecks and angular shards makes the breakup feel solid.
      if (d.tone > 0.56) {
        const angle = d.phase + d.spin * amount;
        const length = size * (2.1 + Math.min(2, Math.abs(d.vz) * 0.55));
        dustCtx.save();
        dustCtx.translate(x, y);
        dustCtx.rotate(angle);
        dustCtx.beginPath();
        dustCtx.moveTo(-length, -size * 0.55);
        dustCtx.lineTo(length, 0);
        dustCtx.lineTo(-length * 0.35, size * 0.8);
        dustCtx.closePath();
        dustCtx.fill();
        dustCtx.restore();
      } else {
        dustCtx.beginPath();
        dustCtx.moveTo(x - tailX, y - tailY);
        dustCtx.lineTo(x + tailX * 0.35, y + tailY * 0.35);
        dustCtx.stroke();
        dustCtx.beginPath();
        dustCtx.arc(x, y, Math.max(0.5, size), 0, Math.PI * 2);
        dustCtx.fill();
      }
    }
    dustCtx.globalAlpha = 1;
  }

  resizeDust();
  on(window, 'resize', resizeDust, { passive: true });

  /* ------------------------------------------------------------------
     4. SCROLL = TIMELINE. One Anime.js timeline moves every structure
        to its own spot in turn; onScroll({ sync }) ties it to the
        scrollbar, so down = separate one by one, up = rebuild.
  ------------------------------------------------------------------ */
  const S = { p: 0, ready: false, lastPointer: -1e9 };
  let tl: AnimeTimeline | null = null, K = 1;

  function hudUpdate(p: number) {
    S.p = p;
    renderDisintegration(p);
    const t = p * 1000;
    let active = -1;
    structs.forEach((st, i) => { if (t >= st.win[0]) active = i; });
    const apart = p > 0.03;
    if (S.ready) {
      hud.dataset.mode = apart ? 'apart' : 'idle';
      hudState.textContent = !apart ? 'assembled · idle'
        : p > 0.97 ? 'exploded · scroll up to rebuild'
        : 'separating: ' + structs[Math.max(active, 0)].name.toLowerCase();
    }
    hudBar.style.width = (p * 100).toFixed(0) + '%';
    labels.classList.toggle('visible', apart);
    labRows.forEach((r, i) => { r.classList.toggle('active', apart && i === active); r.classList.toggle('done', apart && i < active); });
    rig.style.setProperty('--amp', (8 * clamp(p * 6, 0, 1)).toFixed(2));
    rig.classList.toggle('float', apart && !REDUCED);
  }

  function build() {
    if (tl) tl.revert();
    K = (rig.clientWidth / 600) || 1;
    rig.style.setProperty('--K', String(K));
    const timeline = createTimeline({
      defaults: { ease: 'inOutQuad' },
      autoplay: onScroll({ target: $('#track'), enter: 'top top', leave: 'bottom bottom', sync: 0.25 }),
      onUpdate: (self: { currentTime: number }) => hudUpdate(self.currentTime / 1000)
    });
    // Published immediately, but every `.add` below goes through the local:
    // `tl` is reassignable, so TS would widen it back to null inside each
    // callback and the port would need a `!` on every line.
    tl = timeline;
    structs.forEach(st => {
      const dur = st.win[1] - st.win[0], sl = st.slot;
      if (REDUCED) { timeline.add(st.el, { opacity: 0, duration: dur }, st.win[0]); return; }
      timeline.add(st.el, {
        x: (sl.x - (st.ctr[0] - 300)) * K, y: (sl.y - (st.ctr[1] - 210)) * K, z: sl.z * K,
        rotateX: sl.rx, rotateY: sl.ry, rotateZ: sl.rz, scale: sl.s, duration: dur
      }, st.win[0]);
      if (st.multi) st.members.forEach((m) => {
        if (!m.bloom) return;
        const b: Record<string, number> = {};
        for (const k in m.bloom) b[k] = (k === 'x' || k === 'y' || k === 'z') ? m.bloom[k] * K : m.bloom[k];
        timeline.add(m.el as HTMLElement, { ...b, duration: dur }, st.win[0]);
      });
    });

    // FINAL BREAKUP — Anime.js scroll timeline drives the real model pieces.
    // Once the anatomical structures have separated, each SVG component
    // gets its own 3D trajectory: outward X/Y, strong Z depth, and tumbling.
    // Relative values preserve the earlier anatomical separation transforms.
    if (!REDUCED) {
      const explodeAt = 870;
      const explodeDuration = 130;
      structs.forEach(st => {
        const targets = st.multi ? st.members : st.members.slice(0, 1);
        targets.forEach((piece) => {
          const [bx, by, bw, bh] = piece.box;
          const px = bx + bw * 0.5;
          const py = by + bh * 0.5;
          let dx = (px - 300) / 300 + (rnd() - 0.5) * 0.9;
          let dy = (py - 210) / 210 + (rnd() - 0.5) * 0.9;
          const mag = Math.hypot(dx, dy) || 1;
          dx /= mag; dy /= mag;
          const distance = (150 + rnd() * 260) * K;
          const xOut = dx * distance + (rnd() - 0.5) * 110 * K;
          const yOut = dy * distance + (rnd() - 0.5) * 130 * K;
          const zOut = (rnd() < 0.5 ? -1 : 1) * (260 + rnd() * 720) * K;
          const target = piece.el as HTMLElement;
          timeline.add(target, {
            x: `+=${xOut.toFixed(1)}`,
            y: `+=${yOut.toFixed(1)}`,
            z: `+=${zOut.toFixed(1)}`,
            rotateX: `+=${((rnd() - 0.5) * 260).toFixed(1)}deg`,
            rotateY: `+=${((rnd() - 0.5) * 300).toFixed(1)}deg`,
            rotateZ: `+=${((rnd() - 0.5) * 240).toFixed(1)}deg`,
            scale: 0.62 + rnd() * 0.72,
            duration: explodeDuration,
            ease: 'out(3)'
          }, explodeAt);
        });
      });
    }
    // the camera eases back as the eye opens up
    if (!REDUCED) timeline.add(sway, { rotateY: -12, rotateX: 5, z: -120 * K, duration: 1000, ease: 'linear' }, 0);
    else timeline.add(sway, { opacity: 1, duration: 1000, ease: 'linear' }, 0);
    timeline.add(glow, { scale: 1.7, opacity: 0.55, duration: 1000, ease: 'linear' }, 0);
    timeline.add(floor, { scaleX: 1.5, opacity: 0.25, duration: 1000, ease: 'linear' }, 0);
  }
  build();

  let rsT: ReturnType<typeof setTimeout> | null = null;
  on(window, 'resize', () => { if (rsT) clearTimeout(rsT); rsT = setTimeout(build, 250); });

  /* ------------------------------------------------------------------
     5. ALIVE WHEN IDLE: blinking (lids + lashes), eye flicks, follows the cursor
  ------------------------------------------------------------------ */
  let blinkTl: AnimeTimeline | null = null;
  let blinkT: ReturnType<typeof setTimeout> | null = null;
  let sacT: ReturnType<typeof setTimeout> | null = null;
  let doubleBlinkT: ReturnType<typeof setTimeout> | null = null;
  const idle = () => S.ready && S.p < 0.03 && !document.hidden;
  function blink(slow?: boolean) {
    const k = slow ? 1.7 : 1;
    if (blinkTl) blinkTl.pause();
    blinkTl = createTimeline()
      .add(lidFills, { scaleY: 1, duration: 90 * k, ease: 'inQuad' }, 0)
      .add(lashGroups, { scaleY: 0.05, duration: 90 * k, ease: 'inQuad' }, 0)
      .add(lidFills, { scaleY: 0, duration: 150 * k, ease: 'outQuad' }, 140 * k)
      .add(lashGroups, { scaleY: 1, duration: 150 * k, ease: 'outQuad' }, 140 * k);
  }
  function loopBlink(first?: number) {
    if (blinkT) clearTimeout(blinkT);
    blinkT = setTimeout(() => {
      if (idle()) {
        blink();
        // The occasional double blink. Tracked, so unmount cancels it too.
        if (Math.random() < 0.15) {
          doubleBlinkT = setTimeout(() => { if (idle()) blink(); }, 300);
        }
      }
      loopBlink();
    }, first != null ? first : 2500 + Math.random() * 3500);
  }
  function loopSaccade() {
    if (sacT) clearTimeout(sacT);
    sacT = setTimeout(() => {
      if (idle() && performance.now() - S.lastPointer > 2500 && !REDUCED)
        animate(rig, { '--gx': utils.random(-7, 7), '--gy': utils.random(-4, 4), duration: 170, ease: 'outExpo' });
      loopSaccade();
    }, 1200 + Math.random() * 1800);
  }

  // cursor: the whole eye tilts in 3D and the iris/pupil slide toward you
  let px = 0, py = 0, pq = false;
  if (!REDUCED) on(window, 'pointermove', (ev: Event) => {
    const e = ev as PointerEvent;
    if (e.pointerType === 'touch') return;
    S.lastPointer = performance.now();
    px = clamp((e.clientX - innerWidth / 2) / (innerWidth / 2), -1, 1);
    py = clamp((e.clientY - innerHeight / 2) / (innerHeight / 2), -1, 1);
    if (pq) return; pq = true;
    pointerRaf = requestAnimationFrame(() => {
      pq = false;
      animate(rig, { rotateX: -py * 9, rotateY: px * 13, '--gx': px * 14, '--gy': py * 9, duration: 600, ease: 'out(3)' });
    });
  }, { passive: true });

  on(window, 'scroll', () => { if (scrollY > 24) $('#cue').classList.add('gone'); else $('#cue').classList.remove('gone'); if (!S.ready) introTl.complete(); }, { passive: true });
  on(document, 'visibilitychange', () => { if (!document.hidden) { loopBlink(); loopSaccade(); } });

  /* ------------------------------------------------------------------
     6. INTRO: the lid outlines draw themselves, the layers fade in
  ------------------------------------------------------------------ */
  const draw = svg.createDrawable([
    $<SVGElement>('#arc-up'), $<SVGElement>('#arc-low'),
    $<SVGElement>('#crease-up'), $<SVGElement>('#crease-low'),
  ] as unknown as AnimeTarget);
  utils.set(draw, { draw: '0 0' });
  utils.set(fadeInSlices, { opacity: 0 });
  let done = false;
  function endIntro() {
    if (done) return; done = true; S.ready = true;
    utils.set(allSlices, { opacity: 1 });
    utils.set(draw, { draw: '0 1' });
    hudUpdate(S.p);
    loopBlink(900); loopSaccade();
  }
  const introTl = createTimeline({ onComplete: endIntro })
    .add(draw, { draw: ['0 0', '0 1'], duration: 1100, ease: 'inOutQuad', delay: stagger(110) }, 0)
    .add(fadeInSlices, { opacity: [0, 1], duration: 650, ease: 'outQuad', delay: stagger(12) }, 450);

  const handle = {
    S, structs, parts,
    get state() { return S.ready ? (S.p < 0.03 ? 'idle' : 'apart') : 'intro'; },
    get tl() { return tl; },
  };
  (window as unknown as { __eye?: unknown }).__eye = handle;

  /* ------------------------------------------------------------------
     7. TEARDOWN. The source ran until the tab closed. Here the route
        unmounts, and everything above has to stop. Anything left behind
        keeps a scroll observer, a RAF and two setTimeout chains alive
        for the rest of the session, on a device that may be a phone.
  ------------------------------------------------------------------ */
  return function destroy() {
    for (const off of listeners) off();
    listeners.length = 0;

    for (const t of [blinkT, sacT, doubleBlinkT, rsT]) if (t) clearTimeout(t);
    blinkT = sacT = doubleBlinkT = rsT = null;

    if (pointerRaf !== null) cancelAnimationFrame(pointerRaf);
    pointerRaf = null;

    // `tl` owns the onScroll observer, so reverting it is what detaches the
    // scroll listener Anime.js attached for us.
    for (const t of [tl, blinkTl, introTl]) {
      if (!t) continue;
      try { t.pause(); t.revert(); } catch { /* already reverted */ }
    }
    tl = blinkTl = null;

    // The canvas and the generated SVG leave with the React tree, but clear
    // the context first so no captured frame can be reused.
    if (dustCanvas2d) dustCanvas2d.clearRect(0, 0, dustW, dustH);
    rig.replaceChildren();

    if ((window as unknown as { __eye?: unknown }).__eye === handle) {
      delete (window as unknown as { __eye?: unknown }).__eye;
    }
  };
}
