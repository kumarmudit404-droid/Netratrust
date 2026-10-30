/**
 * Route "/" - the landing page, and the app's front door.
 *
 * The markup is `landingMarkup.html`, lifted byte-for-byte out of
 * `netra/ui/landing-source.html` and injected rather than rewritten as JSX.
 * That is deliberate: the file is four `<svg>` blocks and thirty-odd paths of
 * hand-tuned eye anatomy, and hand-converting it to JSX would be a silent
 * chance to change an SVG that nothing here would catch. Injecting it means
 * the DOM is provably the DOM that file shipped.
 *
 * It is not user input and it is not fetched - it is a build-time constant
 * from this repo, so `dangerouslySetInnerHTML` carries no injection risk.
 *
 * The page's own styles live in `landing.css`, scoped to `.landing` plus the
 * `.landing-active` class this component puts on <html> and <body> while it is
 * mounted (see that file's header for why).
 */

import { useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import markup from "./landingMarkup.html?raw"
import { mountEye } from "@/lib/landing/eye"
import "@/landing.css"

/** The five routes the landing page's buttons point at. */
export const LANDING_ROUTES = [
  "/capture",
  "/grade",
  "/sites",
  "/ledger",
  "/referrals",
] as const

/** True for a click the browser should keep: new tab, new window, download. */
function isModifiedClick(e: MouseEvent): boolean {
  return (
    e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey
  )
}

export default function Landing() {
  const hostRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  // `html`/`body` classes: the page's background gradient and its inset frame
  // are painted on those two elements, and neither can be nested under
  // `.landing`. Removed on unmount so /capture gets its own background back.
  useEffect(() => {
    const root = document.documentElement
    const { body } = document
    root.classList.add("landing-active")
    body.classList.add("landing-active")
    return () => {
      root.classList.remove("landing-active")
      body.classList.remove("landing-active")
    }
  }, [])

  // The landing page is one tall scroll track and the eye is driven by scroll
  // position, so arriving from another route has to start at the top.
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [])

  // Build the eye, and tear it down on the way out. StrictMode runs this
  // twice in development, which is the cheapest test there is that `destroy`
  // is complete: a half-teardown shows up immediately as two eyes.
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let destroy: (() => void) | undefined
    try {
      destroy = mountEye(host)
    } catch (err) {
      // A broken decoration must not cost us the front door. The copy, the
      // buttons and the routes they lead to are all plain DOM and still work.
      console.error("[landing] the eye failed to mount; copy still renders", err)
    }
    return () => destroy?.()
  }, [])

  // The buttons carry `data-route` AND a real `href`. One delegated listener
  // turns them into client-side navigation; the href stays the fallback, so
  // the page still works if this effect never runs, and cmd/ctrl-click still
  // opens a new tab.
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const onClick = (e: MouseEvent) => {
      if (isModifiedClick(e)) return
      const target = e.target as Element | null
      const link = target?.closest?.("[data-route]")
      const route = link?.getAttribute("data-route")
      if (!route) return
      e.preventDefault()
      navigate(route)
    }
    host.addEventListener("click", onClick)
    return () => host.removeEventListener("click", onClick)
  }, [navigate])

  return (
    <div
      className="landing"
      ref={hostRef}
      dangerouslySetInnerHTML={{ __html: markup }}
    />
  )
}
