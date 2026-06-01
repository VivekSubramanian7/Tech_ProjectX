import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { ScanStatus } from "@/lib/api";

interface Props {
  scans: ScanStatus[];
  loading?: boolean;
}

function formatTs(ts: string | undefined) {
  if (!ts) return "";
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function ThroughputChart({ scans, loading }: Props) {
  if (loading) {
    return <div className="h-48 rounded bg-muted animate-pulse" />;
  }

  const completed = scans.filter((s) => s.status === "complete" && s.started_ts);

  if (!completed.length) {
    return (
      <div className="h-48 flex items-center justify-center text-sm text-muted-foreground border border-dashed border-border rounded-lg">
        No scans yet — start one to see throughput
      </div>
    );
  }

  const data = completed
    .slice()
    .sort((a, b) => (a.started_ts! > b.started_ts! ? 1 : -1))
    .map((s) => ({
      time: formatTs(s.started_ts),
      files: s.files_scanned,
      findings: s.findings_count,
    }));

  return (
    <div>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="filesGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="hsl(221,70%,42%)" stopOpacity={0.25} />
              <stop offset="95%" stopColor="hsl(221,70%,42%)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(214,20%,88%)" />
          <XAxis dataKey="time" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              borderRadius: 6,
              border: "1px solid hsl(214,20%,88%)",
            }}
          />
          <Area
            type="monotone"
            dataKey="files"
            name="Files scanned"
            stroke="hsl(221,70%,42%)"
            strokeWidth={2}
            fill="url(#filesGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
      {/* Screen-reader table fallback */}
      <table className="sr-only">
        <caption>Files scanned over time</caption>
        <thead>
          <tr>
            <th>Time</th>
            <th>Files scanned</th>
            <th>Findings</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i}>
              <td>{row.time}</td>
              <td>{row.files}</td>
              <td>{row.findings}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
