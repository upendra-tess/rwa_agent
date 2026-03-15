import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
}

const EmptyState = ({ icon, title, description, action }: EmptyStateProps) => (
  <div className="tf-empty-state">
    <div className="tf-empty-icon">{icon}</div>
    <h3 className="tf-empty-title">{title}</h3>
    <p className="tf-empty-desc">{description}</p>
    {action && <div className="tf-empty-action">{action}</div>}
  </div>
);

export default EmptyState;
