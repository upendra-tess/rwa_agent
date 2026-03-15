import { CheckCircle2, Clock, AlertTriangle, XCircle, Loader, Shield, Zap, Calendar } from "lucide-react";

type BadgeVariant =
  | "running" | "waiting" | "scheduled" | "completed" | "failed"
  | "connected" | "disconnected" | "error" | "pending"
  | "low" | "medium" | "high" | "critical"
  | "verified" | "settled" | "refunded"
  | "success" | "aborted" | "info" | "warning" | "action";

interface StatusBadgeProps {
  variant: BadgeVariant;
  label?: string;
  size?: "sm" | "md";
}

const CONFIG: Record<BadgeVariant, { icon: typeof CheckCircle2; className: string; defaultLabel: string }> = {
  running:      { icon: Loader,        className: "sb-running",      defaultLabel: "Running" },
  waiting:      { icon: Clock,         className: "sb-waiting",      defaultLabel: "Waiting" },
  scheduled:    { icon: Calendar,      className: "sb-scheduled",    defaultLabel: "Scheduled" },
  completed:    { icon: CheckCircle2,  className: "sb-completed",    defaultLabel: "Completed" },
  failed:       { icon: XCircle,       className: "sb-failed",       defaultLabel: "Failed" },
  connected:    { icon: CheckCircle2,  className: "sb-connected",    defaultLabel: "Connected" },
  disconnected: { icon: XCircle,       className: "sb-disconnected", defaultLabel: "Disconnected" },
  error:        { icon: XCircle,       className: "sb-error",        defaultLabel: "Error" },
  pending:      { icon: Clock,         className: "sb-pending",      defaultLabel: "Pending" },
  low:          { icon: Shield,        className: "sb-low",          defaultLabel: "Low Risk" },
  medium:       { icon: AlertTriangle, className: "sb-medium",       defaultLabel: "Medium Risk" },
  high:         { icon: AlertTriangle, className: "sb-high",         defaultLabel: "High Risk" },
  critical:     { icon: AlertTriangle, className: "sb-critical",     defaultLabel: "Critical" },
  verified:     { icon: Shield,        className: "sb-verified",     defaultLabel: "Verified" },
  settled:      { icon: CheckCircle2,  className: "sb-settled",      defaultLabel: "Settled" },
  refunded:     { icon: Zap,           className: "sb-refunded",     defaultLabel: "Refunded" },
  success:      { icon: CheckCircle2,  className: "sb-success",      defaultLabel: "Success" },
  aborted:      { icon: XCircle,       className: "sb-aborted",      defaultLabel: "Aborted" },
  info:         { icon: Zap,           className: "sb-info",         defaultLabel: "Info" },
  warning:      { icon: AlertTriangle, className: "sb-warning",      defaultLabel: "Warning" },
  action:       { icon: Zap,           className: "sb-action",       defaultLabel: "Action" },
};

const StatusBadge = ({ variant, label, size = "sm" }: StatusBadgeProps) => {
  const cfg = CONFIG[variant] ?? CONFIG.pending;
  const Icon = cfg.icon;
  const isSpinning = variant === "running";

  return (
    <span className={`status-badge ${cfg.className} ${size === "md" ? "sb-md" : ""}`}>
      <Icon size={size === "md" ? 12 : 10} strokeWidth={2} className={isSpinning ? "spin" : ""} />
      {label ?? cfg.defaultLabel}
    </span>
  );
};

export default StatusBadge;
