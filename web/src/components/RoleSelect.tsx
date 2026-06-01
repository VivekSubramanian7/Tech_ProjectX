import { ShieldCheck, User } from "lucide-react";
import { DEMO_OWNERS } from "@/lib/api";
import { useRole } from "@/lib/rbac";

export default function RoleSelect() {
  const { setRole, enterAsOwner } = useRole();

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="max-w-lg w-full px-6">
        <h1 className="text-2xl font-semibold text-foreground mb-2">GDPR Data Discovery</h1>
        <p className="text-muted-foreground mb-8 text-sm">
          Select your role to continue (demo — no SSO in MVP)
        </p>

        <button
          onClick={() => setRole("admin")}
          className="w-full flex items-center gap-4 p-5 rounded-lg border border-border bg-card hover:bg-accent transition-colors focus-visible:outline focus-visible:outline-2 mb-6"
        >
          <ShieldCheck className="w-8 h-8 text-primary shrink-0" />
          <div className="text-left">
            <span className="font-medium text-sm block">DPO / Admin</span>
            <span className="text-xs text-muted-foreground">Trigger scans · view dashboard</span>
          </div>
        </button>

        <p className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
          Data owner
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {DEMO_OWNERS.map((owner) => (
            <button
              key={owner.id}
              onClick={() => enterAsOwner(owner.id)}
              className="flex flex-col items-start gap-2 p-5 rounded-lg border border-border bg-card hover:bg-accent transition-colors focus-visible:outline focus-visible:outline-2 text-left"
            >
              <User className="w-7 h-7 text-primary" />
              <span className="font-medium text-sm">{owner.label}</span>
              <span className="text-xs text-muted-foreground">{owner.hint}</span>
              <span className="text-xs font-mono text-muted-foreground/80">{owner.id}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
