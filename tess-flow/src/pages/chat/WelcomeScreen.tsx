import { Sparkles, ArrowRight } from "lucide-react";
import { Agent } from "../../types";
import ChatInput from "./ChatInput";

interface WelcomeScreenProps {
  onSend: (text: string, mentionedAgent?: Agent) => void;
}

const SUGGESTION_PROMPTS = [
  "Research the latest trends in AI agent frameworks",
  "Review my Solidity smart contract for security issues",
  "Reconcile all USDC invoices from last week",
  "Analyse my portfolio and suggest rebalancing",
];

const WelcomeScreen = ({ onSend }: WelcomeScreenProps) => {
  return (
    <div className="welcome-screen">
      <div className="welcome-content">
        <div className="welcome-logo-wrap">
          <img src="/tesseris-logo.png" alt="TessFlow" className="welcome-logo" />
        </div>

        <h1 className="welcome-title">What can I help you with?</h1>
        <p className="welcome-subtitle">
          Just describe your task — TessFlow will automatically route it to the right agent.
        </p>

        <div className="welcome-suggestions">
          <p className="welcome-suggestions-label">
            <Sparkles size={13} strokeWidth={2} />
            Try asking
          </p>
          <div className="welcome-suggestions-grid">
            {SUGGESTION_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="welcome-suggestion-chip"
                onClick={() => onSend(prompt)}
              >
                <span>{prompt}</span>
                <ArrowRight size={12} strokeWidth={2} className="welcome-suggestion-arrow" />
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="welcome-input-wrap">
        <ChatInput onSend={onSend} />
      </div>
    </div>
  );
};

export default WelcomeScreen;
