import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { FascicoloPage } from "@/features/fascicoli/FascicoloPage";
import { RedazioneAttiPage } from "@/features/atti/RedazioneAttiPage";
import { TelematicoWorkspacePage } from "@/features/telematico/TelematicoWorkspacePage";
import { EconomiaPage } from "@/features/economia/EconomiaPage";
import { AdminPage } from "@/features/admin/AdminPage";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/fascicoli/:id?" element={<FascicoloPage />} />
        <Route path="/redazione-atti" element={<RedazioneAttiPage />} />
        <Route path="/telematico" element={<TelematicoWorkspacePage />} />
        <Route path="/economia" element={<EconomiaPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </AppShell>
  );
}
