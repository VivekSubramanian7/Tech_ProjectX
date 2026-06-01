import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useRole, type Role } from "@/lib/rbac";

export function RbacGuard({ allow, children }: { allow: Role; children: ReactNode }) {
  const { role } = useRole();
  if (role !== allow) return <Navigate to="/" replace />;
  return <>{children}</>;
}
