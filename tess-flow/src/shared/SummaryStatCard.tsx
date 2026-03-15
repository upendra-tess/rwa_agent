import type { ReactNode } from "react";

interface SummaryStatCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  accent?: "teal" | "green" | "amber" | "red" | "blue" | "muted";
}

const SummaryStatCard = ({ label, value, icon, accent = "teal" }: SummaryStatCardProps) => (
  <div className={`tf-stat-card tf-stat-${accent}`}>
    {icon && <div className="tf-stat-icon">{icon}</div>}
    <div className="tf-stat-value">{value}</div>
    <div className="tf-stat-label">{label}</div>
  </div>
);

export default SummaryStatCard;
