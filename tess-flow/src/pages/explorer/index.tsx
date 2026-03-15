import { useState } from "react";

const EXPLORER_URL = "https://explorer.tesseris.org";

const ExplorerPage = () => {
  const [isLoaded, setIsLoaded] = useState(false);

  return (
    <div className="tf-explorer-page">
      <div className="tf-explorer-shell">
        {!isLoaded && (
          <div className="tf-explorer-loading" aria-live="polite">
            <span className="tf-explorer-spinner" aria-hidden="true" />
            <span>Loading Explorer...</span>
          </div>
        )}
        <iframe
          className={`tf-explorer-frame ${isLoaded ? "loaded" : "loading"}`}
          src={EXPLORER_URL}
          title="Tesseris Explorer"
          loading="lazy"
          referrerPolicy="strict-origin-when-cross-origin"
          onLoad={() => setIsLoaded(true)}
        />
      </div>
    </div>
  );
};

export default ExplorerPage;
