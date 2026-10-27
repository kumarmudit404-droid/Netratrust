import { Navigate, Route, Routes } from "react-router-dom"
import { TopNav } from "@/components/TopNav"
import Capture from "@/routes/Capture"
import Grade from "@/routes/Grade"
import Referrals from "@/routes/Referrals"
import Sites from "@/routes/Sites"
import Ledger from "@/routes/Ledger"

export default function App() {
  return (
    <div className="min-h-dvh bg-bg">
      <TopNav />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/capture" replace />} />
          <Route path="/capture" element={<Capture />} />
          <Route path="/grade" element={<Grade />} />
          <Route path="/referrals" element={<Referrals />} />
          <Route path="/sites" element={<Sites />} />
          <Route path="/ledger" element={<Ledger />} />
        </Routes>
      </main>
    </div>
  )
}
