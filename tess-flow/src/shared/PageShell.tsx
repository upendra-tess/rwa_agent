import type { ReactNode } from "react";

interface PageShellProps {
  children: ReactNode;
  className?: string;
}

const PageShell = ({ children, className = "" }: PageShellProps) => (
  <div className={`tf-page-shell ${className}`}>
    {children}
  </div>
);

export default PageShell;
