import type { ReactNode } from "react";
import { cn } from "../lib/utils";

// `.state-wrap`/`.state-card` per overview-empty.html/overview-disconnected.
// html/sessions-list-empty.html - the centered full-page (or full-panel)
// state shared by every "nothing to show, here's why" screen.
interface StateCardProps {
  icon: ReactNode;
  title: string;
  body: ReactNode;
  err?: boolean;
  children?: ReactNode;
  "data-testid"?: string;
}

export function StateCard({ icon, title, body, err, children, "data-testid": testId }: StateCardProps) {
  return (
    <div className="state-wrap" data-testid={testId}>
      <div className="state-card">
        <div className={cn("state-icon", err && "err")}>{icon}</div>
        <div className="state-title">{title}</div>
        <div className="state-body" style={err ? { color: "var(--remove)" } : undefined}>
          {body}
        </div>
        {children}
      </div>
    </div>
  );
}
