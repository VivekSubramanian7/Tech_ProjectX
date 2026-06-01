import type { OwnerFinding } from "@/lib/api";

export const ALL_FILTER = "";

const CATEGORY_FILTER_PREFIX = "gdpr_owner_category_filter_";
const FILE_TYPE_FILTER_PREFIX = "gdpr_owner_file_type_filter_";

export function categoryFilterKey(userId: string): string {
  return `${CATEGORY_FILTER_PREFIX}${userId}`;
}

export function fileTypeFilterKey(userId: string): string {
  return `${FILE_TYPE_FILTER_PREFIX}${userId}`;
}

export function loadStoredFilter(key: string): string {
  return localStorage.getItem(key) ?? ALL_FILTER;
}

/** File extension from catalog path, or a bucket label for odd paths. */
export function fileTypeKey(filePath: string): string {
  const name = filePath.split(/[/\\]/).pop() ?? filePath;
  const dot = name.lastIndexOf(".");
  if (dot > 0 && dot < name.length - 1) {
    return name.slice(dot).toLowerCase();
  }
  if (filePath.startsWith("onedrive://")) {
    return "onedrive";
  }
  return "other";
}

export function fileTypeLabel(key: string): string {
  if (key === ALL_FILTER) return "All file types";
  if (key === "other") return "Other / no extension";
  if (key === "onedrive") return "OneDrive";
  return key;
}

export interface CategoryOption {
  code: string;
  label: string;
  count: number;
}

export interface FileTypeOption {
  key: string;
  label: string;
  count: number;
}

export function buildCategoryOptions(findings: OwnerFinding[]): CategoryOption[] {
  const map = new Map<string, CategoryOption>();
  for (const f of findings) {
    const existing = map.get(f.classification_code);
    if (existing) {
      existing.count += 1;
    } else {
      map.set(f.classification_code, {
        code: f.classification_code,
        label: f.display_label,
        count: 1,
      });
    }
  }
  return [...map.values()].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

export function buildFileTypeOptions(findings: OwnerFinding[]): FileTypeOption[] {
  const map = new Map<string, number>();
  for (const f of findings) {
    const key = fileTypeKey(f.file_path);
    map.set(key, (map.get(key) ?? 0) + 1);
  }
  return [...map.entries()]
    .map(([key, count]) => ({ key, label: fileTypeLabel(key), count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

export function filterFindings(
  findings: OwnerFinding[],
  categoryCode: string,
  fileType: string
): OwnerFinding[] {
  return findings.filter((f) => {
    if (categoryCode && f.classification_code !== categoryCode) {
      return false;
    }
    if (fileType && fileTypeKey(f.file_path) !== fileType) {
      return false;
    }
    return true;
  });
}

export function filtersActive(categoryCode: string, fileType: string): boolean {
  return Boolean(categoryCode || fileType);
}
