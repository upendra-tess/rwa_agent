import type { ReactNode } from "react";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  actions?: ReactNode;
}

const SectionHeader = ({ title, subtitle, icon, actions }: SectionHeaderProps) => (
  <div className="tf-section-header">
    <div className="tf-section-header-left">
      {icon && <span className="tf-section-header-icon">{icon}</span>}
      <div>
        <h2 className="tf-section-title">{title}</h2>
        {subtitle && <p className="tf-section-subtitle">{subtitle}</p>}
      </div>
    </div>
    {actions && <div className="tf-section-header-actions">{actions}</div>}
  </div>
);

export default SectionHeader;
