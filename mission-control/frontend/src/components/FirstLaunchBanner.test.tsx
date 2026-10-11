import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FirstLaunchBanner } from "./FirstLaunchBanner";

describe("FirstLaunchBanner", () => {
  it("renders the scanned/total count and scales the progress fill", () => {
    render(<FirstLaunchBanner scanned={3} total={5} />);

    expect(screen.getByText("Backfilling history — 3 of 5 known projects scanned")).toBeInTheDocument();
    const fill = screen.getByTestId("first-launch-banner").querySelector(".progress-fill") as HTMLElement;
    expect(fill.style.width).toBe("60%");
  });

  it("doesn't divide by zero when total is 0", () => {
    render(<FirstLaunchBanner scanned={0} total={0} />);
    const fill = screen.getByTestId("first-launch-banner").querySelector(".progress-fill") as HTMLElement;
    expect(fill.style.width).toBe("0%");
  });
});
