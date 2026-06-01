import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import AdminPage from "./admin/AdminPage";
import OwnerPage from "./owner/OwnerPage";
import { RbacGuard } from "./components/RbacGuard";
import { RoleProvider, useRole } from "./lib/rbac";
import RoleSelect from "./components/RoleSelect";

function AppRoutes() {
  const { role } = useRole();

  if (!role) return <RoleSelect />;

  return (
    <Routes>
      <Route path="/" element={<Navigate to={role === "admin" ? "/admin" : "/owner"} replace />} />
      <Route
        path="/admin/*"
        element={
          <RbacGuard allow="admin">
            <AdminPage />
          </RbacGuard>
        }
      />
      <Route
        path="/owner/*"
        element={
          <RbacGuard allow="owner">
            <OwnerPage />
          </RbacGuard>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <RoleProvider>
      <BrowserRouter>
        <AppRoutes />
        <Toaster position="bottom-right" richColors closeButton />
      </BrowserRouter>
    </RoleProvider>
  );
}
