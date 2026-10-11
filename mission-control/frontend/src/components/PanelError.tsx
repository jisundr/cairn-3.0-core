import { AlertTriangleIcon } from "./icons";

// `.err-text` + `.btn-err` per overview-error.html/sessions-list-error.html/
// drilldown-error.html - goal 2's per-component error state. Each screen
// wraps these two pieces in its own layout (`.err-inline` for a panel-sized
// error, a centered flex column for a full-page error, a horizontal banner
// for Drilldown's page-level partial-failure notice), so this component
// renders only the pieces themselves, not a fixed wrapper.
interface PanelErrorProps {
  message: string;
  onRetry: () => void;
  testId?: string;
}

export function PanelError({ message, onRetry, testId }: PanelErrorProps) {
  return (
    <>
      <span className="err-text" data-testid={testId ? `${testId}-text` : undefined}>
        <AlertTriangleIcon />
        {message}
      </span>
      <button className="btn-err" onClick={onRetry} data-testid={testId ? `${testId}-retry` : "panel-error-retry"}>
        Retry
      </button>
    </>
  );
}
