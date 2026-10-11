import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TruncatedAxisTick } from "./TruncatedAxisTick";

describe("TruncatedAxisTick", () => {
  it("truncates a long label with an ellipsis, carrying the full name in a title", () => {
    const { container } = render(
      <svg>
        <TruncatedAxisTick x={0} y={0} payload={{ value: "impeccable:impeccable-finish-reviewer" }} />
      </svg>,
    );

    const text = container.querySelector("text");
    expect(text?.textContent).not.toEqual("impeccable:impeccable-finish-reviewer");
    expect(text?.textContent).toMatch(/…$/);
    expect(container.querySelector("title")?.textContent).toEqual("impeccable:impeccable-finish-reviewer");
  });

  it("renders a short label unchanged, with no truncation", () => {
    const { container } = render(
      <svg>
        <TruncatedAxisTick x={0} y={0} payload={{ value: "builder" }} />
      </svg>,
    );

    expect(container.querySelector("text")?.textContent).toEqual("builder");
  });
});
