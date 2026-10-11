import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RangeControl } from "./RangeControl";

describe("RangeControl", () => {
  it("marks the selected range active and calls onChange for a different one", () => {
    const onChange = vi.fn();
    render(<RangeControl value="7d" onChange={onChange} />);

    expect(screen.getByTestId("range-seg-7d")).toHaveClass("active");
    expect(screen.getByTestId("range-seg-30d")).not.toHaveClass("active");

    fireEvent.click(screen.getByTestId("range-seg-30d"));
    expect(onChange).toHaveBeenCalledWith("30d");
  });

  it("is keyboard-activatable", () => {
    const onChange = vi.fn();
    render(<RangeControl value="7d" onChange={onChange} />);

    fireEvent.keyDown(screen.getByTestId("range-seg-life"), { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("life");
  });
});
