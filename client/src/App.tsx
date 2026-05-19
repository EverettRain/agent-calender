import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import Today from "@/pages/Today";
import Calendar from "@/pages/Calendar";
import Manage from "@/pages/Manage";
import Settings from "@/pages/Settings";
import { useSettings } from "@/store/settings";
import { useSSE } from "@/hooks/useSSE";
import { useTheme } from "@/hooks/useTheme";

export default function App() {
  const isConfigured = useSettings((s) => s.isConfigured());
  useTheme();
  useSSE();

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route
          index
          element={isConfigured ? <Today /> : <Navigate to="/settings" replace />}
        />
        <Route path="calendar" element={<Calendar />} />
        <Route path="manage" element={<Manage />} />
        <Route path="settings" element={<Settings />} />
        <Route path="settings/:tab" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
