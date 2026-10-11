import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PanelError } from "./PanelError";

describe("PanelError", () => {
  it("shows the message and calls onRetry when Retry is clicked", () => {
    const onRetry = vi.fn();
    render(<PanelError message="Couldn't load — request failed" onRetry={onRetry} testId="by-tool-error" />);

    expect(screen.getByText("Couldn't load — request failed")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("by-tool-error-retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
