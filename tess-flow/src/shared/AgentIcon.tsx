import {
  FlaskConical,
  Code2,
  CreditCard,
  BarChart3,
  Shield,
  TrendingUp,
  Mail,
  CalendarDays,
  Globe,
  Megaphone,
  Bot,
} from "lucide-react";
import { AgentIconName } from "../types";

const ICON_MAP: Record<AgentIconName, typeof Bot> = {
  FlaskConical,
  Code2,
  CreditCard,
  BarChart3,
  Shield,
  TrendingUp,
  Mail,
  CalendarDays,
  Globe,
  Megaphone,
};

interface AgentIconProps {
  name: AgentIconName;
  size?: number;
  className?: string;
}

const AgentIcon = ({ name, size = 18, className }: AgentIconProps) => {
  const Icon = ICON_MAP[name] ?? Bot;
  return <Icon size={size} className={className} />;
};

export default AgentIcon;
