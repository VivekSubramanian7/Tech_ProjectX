import type { OwnerFinding } from "@/lib/api";
import { highestRisk, riskRank, type RiskWeight } from "@/lib/risk";

export interface FileCategorySummary {
  code: string;
  label: string;
  count: number;
  risk_weight: RiskWeight;
}

export interface FileGroup {
  file_id: string;
  file_path: string;
  file_name: string;
  findings: OwnerFinding[];
  categories: FileCategorySummary[];
  highestRisk: RiskWeight;
  findingIds: number[];
}

function fileNameFromPath(filePath: string): string {
  const parts = filePath.split(/[/\\]/);
  return parts[parts.length - 1] || filePath;
}

function buildCategories(findings: OwnerFinding[]): FileCategorySummary[] {
  const map = new Map<string, FileCategorySummary>();
  for (const f of findings) {
    const existing = map.get(f.classification_code);
    if (existing) {
      existing.count += 1;
      if (riskRank(f.risk_weight) > riskRank(existing.risk_weight)) {
        existing.risk_weight = f.risk_weight;
      }
    } else {
      map.set(f.classification_code, {
        code: f.classification_code,
        label: f.display_label,
        count: 1,
        risk_weight: f.risk_weight,
      });
    }
  }
  return [...map.values()].sort(
    (a, b) =>
      riskRank(b.risk_weight) - riskRank(a.risk_weight) ||
      b.count - a.count ||
      a.label.localeCompare(b.label)
  );
}

export function countUniqueFiles(findings: OwnerFinding[]): number {
  return new Set(findings.map((f) => f.file_id)).size;
}

export function groupFindingsByFile(findings: OwnerFinding[]): FileGroup[] {
  const byFile = new Map<string, OwnerFinding[]>();
  for (const f of findings) {
    const list = byFile.get(f.file_id) ?? [];
    list.push(f);
    byFile.set(f.file_id, list);
  }

  const groups: FileGroup[] = [];
  for (const [file_id, fileFindings] of byFile) {
    const sorted = [...fileFindings].sort(
      (a, b) => riskRank(b.risk_weight) - riskRank(a.risk_weight) || a.id - b.id
    );
    groups.push({
      file_id,
      file_path: sorted[0].file_path,
      file_name: fileNameFromPath(sorted[0].file_path),
      findings: sorted,
      categories: buildCategories(sorted),
      highestRisk: highestRisk(sorted.map((f) => f.risk_weight)),
      findingIds: sorted.map((f) => f.id),
    });
  }

  return groups.sort(
    (a, b) =>
      riskRank(b.highestRisk) - riskRank(a.highestRisk) ||
      b.findings.length - a.findings.length ||
      a.file_name.localeCompare(b.file_name)
  );
}
