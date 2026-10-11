import type { CSSProperties, ReactNode } from "react";
import { cn } from "../lib/utils";

// `.panel`/`.panel-title` per design.css - the base card every rollup,
// chart, and table sits in. `err` swaps both to their `.err` modifier
// (goal 2's error-state border/title color) - the panel's body content
// (PanelError's pieces, wrapped in `.err-inline` by the caller) is left to
// the caller, since the wrapper layout differs per screen.
interface PanelProps {
  children: ReactNode;
  err?: boolean;
  className?: string;
  style?: CSSProperties;
  "data-testid"?: string;
}

export function Panel({ children, err, className, style, "data-testid": testId }: PanelProps) {
  return (
    <div className={cn("panel", err && "err", className)} style={style} data-testid={testId}>
      {children}
    </div>
  );
}

interface PanelTitleProps {
  children: ReactNode;
  err?: boolean;
  style?: CSSProperties;
}

export function PanelTitle({ children, err, style }: PanelTitleProps) {
  return (
    <div className={cn("panel-title", err && "err")} style={style}>
      {children}
    </div>
  );
}
