import {
  Wallet,
  Share2,
  Headphones,
  Clock,
} from "lucide-react";
import { useState, useEffect } from "react";

interface ActivityBarProps {
  onNavigateToWallet?: () => void;
  onNavigateToIntegrations?: () => void;
}

const ActivityBar = ({
  onNavigateToWallet,
  onNavigateToIntegrations,
}: ActivityBarProps) => {
  const [currentTime, setCurrentTime] = useState(new Date());

  // Update time every minute
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 60000);
    return () => clearInterval(interval);
  }, []);

  const formattedTime = currentTime.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <footer className="activity-bar-bottom">
      <div className="ab-section ab-right">
        <button
          type="button"
          className="ab-quick-link"
          onClick={onNavigateToWallet}
          title="Wallet integration"
        >
          <Wallet size={12} strokeWidth={2} />
          <span>Wallet</span>
        </button>

        <button
          type="button"
          className="ab-quick-link"
          onClick={onNavigateToIntegrations}
          title="Social integrations"
        >
          <Share2 size={12} strokeWidth={2} />
          <span>Socials</span>
        </button>

        <button
          type="button"
          className="ab-quick-link"
          title="Support"
          onClick={() => window.open("https://docs.tesseris.io", "_blank", "noopener,noreferrer")}
        >
          <Headphones size={12} strokeWidth={2} />
          <span>Support</span>
        </button>

        <div className="ab-divider" />

        <div className="ab-time" title="Current time">
          <Clock size={11} strokeWidth={2} />
          <span>{formattedTime}</span>
        </div>
      </div>
    </footer>
  );
};

export default ActivityBar;
