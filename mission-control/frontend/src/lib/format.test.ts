import { describe, expect, it } from "vitest";
import {
  compareVersions,
  formatActivityStamp,
  formatCairnVersion,
  formatDateLabel,
  formatLastTouched,
  taskDisplayName,
} from "./format";

describe("formatDateLabel", () => {
  it("omits the year when the date falls in the given now's year", () => {
    expect(formatDateLabel("2026-09-28", new Date(Date.UTC(2026, 5, 1)))).toEqual("Sep 28, Mon");
  });

  it("shows the literal year, unparenthesized, when it differs from the given now's year", () => {
    expect(formatDateLabel("2019-01-05", new Date(Date.UTC(2026, 5, 1)))).toEqual("Jan 5 2019, Sat");
  });
});

describe("taskDisplayName", () => {
  it("strips a top-level task folder's date/time prefix", () => {
    expect(taskDisplayName("docs/tasks/2026-09-28-1345-build-kanban-board")).toBe("build-kanban-board");
  });

  it("leaves a sub-task folder's numeric prefix as-is (it has no date to strip)", () => {
    expect(taskDisplayName("docs/tasks/2026-09-28-1345-build-kanban-board/02-heartbeat-hooks")).toBe(
      "02-heartbeat-hooks",
    );
  });
});

describe("formatLastTouched", () => {
  it("renders relative time from the date and UTC time when a time is present", () => {
    const now = new Date("2026-09-29T10:00:00Z");
    expect(formatLastTouched("2026-09-28", "11:00", now)).toBe("23h ago");
    expect(formatLastTouched("2026-09-29", "09:45", now)).toBe("15m ago");
  });

  it("switches to days from 24 hours on", () => {
    const now = new Date("2026-09-29T10:00:00Z");
    expect(formatLastTouched("2026-09-28", "10:00", now)).toBe("1d ago");
    expect(formatLastTouched("2026-09-28", "09:00", now)).toBe("1d ago");
    expect(formatLastTouched("2026-09-22", "10:00", now)).toBe("7d ago");
  });

  it("falls back to the date label for a future time beyond the skew allowance", () => {
    const now = new Date("2026-09-29T10:00:00Z");
    expect(formatLastTouched("2026-09-29", "10:15", now)).toBe(formatDateLabel("2026-09-29", now));
  });

  it("treats a small future skew as just now", () => {
    const now = new Date("2026-09-29T10:00:00Z");
    expect(formatLastTouched("2026-09-29", "10:02", now)).toBe("0s ago");
  });

  it("falls back to the date label when the time is empty", () => {
    const now = new Date("2026-09-29T10:00:00Z");
    expect(formatLastTouched("2019-01-05", "", now)).toBe(formatDateLabel("2019-01-05", now));
  });
});

describe("formatActivityStamp", () => {
  const now = new Date("2026-09-29T10:00:00Z");

  it("renders relative time for a single-day entry with a time", () => {
    expect(formatActivityStamp("2026-09-29", "09:45", now)).toBe("15m ago");
  });

  it("keeps the raw date when the entry has no time", () => {
    expect(formatActivityStamp("2026-09-23", null, now)).toBe("2026-09-23");
  });

  it("keeps a date range raw even when it carries a time", () => {
    expect(formatActivityStamp("2026-09-28/29", "09:00", now)).toBe("2026-09-28/29");
  });

  it("falls back to the date label for a time beyond the future skew allowance", () => {
    expect(formatActivityStamp("2026-09-29", "10:15", now)).toBe(formatDateLabel("2026-09-29", now));
  });
});

describe("formatCairnVersion", () => {
  it("prefixes a recorded version with cairn", () => {
    expect(formatCairnVersion("0.40.0")).toBe("cairn 0.40.0");
  });

  it("reads unknown when no version was recorded", () => {
    expect(formatCairnVersion(null)).toBe("cairn unknown");
    expect(formatCairnVersion(undefined)).toBe("cairn unknown");
  });
});

describe("compareVersions", () => {
  it("orders by numeric major, minor, then patch rather than as text", () => {
    expect(compareVersions("0.9.0", "0.10.0")).toBeLessThan(0);
    expect(compareVersions("1.0.0", "0.99.99")).toBeGreaterThan(0);
    expect(compareVersions("0.40.2", "0.40.10")).toBeLessThan(0);
  });

  it("treats equal cores as equal whatever the suffix", () => {
    expect(compareVersions("0.40.0", "0.40.0")).toBe(0);
    expect(compareVersions("0.40.0-rc.1", "0.40.0")).toBe(0);
  });

  it("treats input it cannot parse as equal to anything", () => {
    expect(compareVersions("unknown", "0.40.0")).toBe(0);
    expect(compareVersions("0.40.0", "1.2")).toBe(0);
  });
});
