import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "@/components/Layout";
import Today from "@/pages/Today";
import Settings from "@/pages/Settings";
import { useSettings } from "@/store/settings";
import { useSSE } from "@/hooks/useSSE";

export default function App() {
  const isConfigured = useSettings((s) => s.isConfigured());
  useSSE();

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route
          index
          element={isConfigured ? <Today /> : <Navigate to="/settings" replace />}
        />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
