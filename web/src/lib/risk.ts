/** Risk edge colours — shared by admin breakdown and owner finding cards. */
export const RISK_EDGE: Record<string, string> = {
  Critical: "bg-risk-critical",
  High: "bg-risk-high",
  Medium: "bg-risk-medium",
  Low: "bg-risk-low",
};

export type RiskWeight = keyof typeof RISK_EDGE;

const RISK_RANK: Record<RiskWeight, number> = {
  Critical: 4,
  High: 3,
  Medium: 2,
  Low: 1,
};

export function riskRank(weight: RiskWeight): number {
  return RISK_RANK[weight] ?? 0;
}

export function highestRisk(weights: RiskWeight[]): RiskWeight {
  if (weights.length === 0) return "Low";
  return weights.reduce((best, w) => (riskRank(w) > riskRank(best) ? w : best));
}
