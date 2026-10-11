import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WarningBanner } from "./WarningBanner";
import type { UsageLimitEvent } from "../api/types";

const event: UsageLimitEvent = {
  id: 1,
  session_id: "sess-1",
  timestamp: "2026-09-27T00:00:00Z",
  raw_entry: "usage limit hit",
  project: "test-project",
};

describe("WarningBanner", () => {
  it("renders nothing when there are no events", () => {
    render(<WarningBanner events={[]} />);
    expect(screen.queryByTestId("usage-limit-banner")).not.toBeInTheDocument();
  });

  it("reports the event count, singular and plural", () => {
    const { rerender } = render(<WarningBanner events={[event]} />);
    expect(screen.getByTestId("usage-limit-banner")).toHaveTextContent("once");

    rerender(<WarningBanner events={[event, { ...event, id: 2 }]} />);
    expect(screen.getByTestId("usage-limit-banner")).toHaveTextContent("2 times");
  });
});
