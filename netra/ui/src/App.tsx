import { Outlet, Route, Routes } from "react-router-dom"
import { TopNav } from "@/components/TopNav"
import Landing from "@/routes/Landing"
import Capture from "@/routes/Capture"
import Grade from "@/routes/Grade"
import Referrals from "@/routes/Referrals"
import Sites from "@/routes/Sites"
import Ledger from "@/routes/Ledger"

/**
 * The chrome the five screening routes share. Unchanged from when it was
 * inlined in App: same wrapper, same TopNav, same <main>.
 *
 * It is a layout route now only so that "/" can sit outside it. The landing
 * page is full-bleed, brings its own header (`.atelier`) and its own
 * navigation (the `data-route` buttons), and paints `html`/`body` itself - so
 * TopNav and `bg-bg` would both fight it.
 */
function ScreeningChrome() {
  return (
    <div className="min-h-dvh bg-bg">
      <TopNav />
      <main>
        <Outlet />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route element={<ScreeningChrome />}>
        <Route path="/capture" element={<Capture />} />
        <Route path="/grade" element={<Grade />} />
        <Route path="/referrals" element={<Referrals />} />
        <Route path="/sites" element={<Sites />} />
        <Route path="/ledger" element={<Ledger />} />
      </Route>
    </Routes>
  )
}
