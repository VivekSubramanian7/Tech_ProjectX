import { createContext, useContext, useState, type ReactNode } from "react";
import { DEMO_OWNER_ID, DEMO_OWNERS } from "@/lib/api";

const OWNER_USER_KEY = "gdpr_owner_id";

export type Role = "admin" | "owner" | null;

function normalizeOwnerId(id: string | null): string {
  if (id && DEMO_OWNERS.some((o) => o.id === id)) {
    return id;
  }
  return DEMO_OWNER_ID;
}

interface RoleCtx {
  role: Role;
  ownerUserId: string;
  setRole: (r: Role) => void;
  setOwnerUserId: (id: string) => void;
  enterAsOwner: (id: string) => void;
}

const Ctx = createContext<RoleCtx>({
  role: null,
  ownerUserId: DEMO_OWNER_ID,
  setRole: () => {},
  setOwnerUserId: () => {},
  enterAsOwner: () => {},
});

export function RoleProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<Role>(() => {
    const stored = localStorage.getItem("gdpr_role");
    return stored === "admin" || stored === "owner" ? stored : null;
  });

  const [ownerUserId, setOwnerUserIdState] = useState(() =>
    normalizeOwnerId(localStorage.getItem(OWNER_USER_KEY))
  );

  const setOwnerUserId = (id: string) => {
    const normalized = normalizeOwnerId(id);
    localStorage.setItem(OWNER_USER_KEY, normalized);
    setOwnerUserIdState(normalized);
  };

  const setRole = (r: Role) => {
    if (r) localStorage.setItem("gdpr_role", r);
    else localStorage.removeItem("gdpr_role");
    setRoleState(r);
  };

  const enterAsOwner = (id: string) => {
    setOwnerUserId(id);
    setRole("owner");
  };

  return (
    <Ctx.Provider value={{ role, ownerUserId, setRole, setOwnerUserId, enterAsOwner }}>
      {children}
    </Ctx.Provider>
  );
}

export function useRole() {
  return useContext(Ctx);
}
