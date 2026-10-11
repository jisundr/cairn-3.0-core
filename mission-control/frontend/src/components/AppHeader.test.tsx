import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TaskCard } from "../api/types";
import { BASE_TITLE, _resetAttentionModuleStateForTests } from "../lib/attention";
import { envelope, installFetchMock } from "../test/mockApi";
import { AppHeader } from "./AppHeader";

function task(overrides: Partial<TaskCard> = {}): TaskCard {
  return {
    project: "cairn-2.0",
    folder: "docs/tasks/2026-09-28-slug",
    parent: null,
    kind: "build",
    goal: "goal",
    key_info: "needs-human",
    last_log_date: "2026-09-28",
    last_log_time: "",
    column: "building",
    active: false,
    needs_attention: true,
    done: false,
    sub_tasks: null,
    ...overrides,
  };
}

// AppHeader itself calls useTasks() internally (PRD §6.9 - the pill/title/
// favicon/chime all read the same polled /api/tasks response, from
// whichever tab AppHeader happens to be mounted on) - every render needs a
// QueryClient and a handled /api/tasks route, even for tests that aren't
// about attention signaling at all.
function renderHeader(client: QueryClient, props: Partial<React.ComponentProps<typeof AppHeader>> = {}) {
  return render(
    <QueryClientProvider client={client}>
      <AppHeader
        activeTab="overview"
        onTabChange={() => {}}
        connected
        onRefresh={() => {}}
        updatedLabel={null}
        {...props}
      />
    </QueryClientProvider>,
  );
}

function newClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } });
}

describe("AppHeader", () => {
  beforeEach(() => {
    _resetAttentionModuleStateForTests();
    localStorage.clear();
    document.title = BASE_TITLE;
  });

  afterEach(() => {
    document.title = BASE_TITLE;
  });

  it("renders the refresh button spinning, disabled and busy only while refreshing", async () => {
    installFetchMock({ "/api/tasks": () => envelope([]) });
    const view = renderHeader(newClient(), { refreshing: true });

    const busy = screen.getByRole("button", { name: "Refresh now" });
    expect(busy).toBeDisabled();
    expect(busy).toHaveAttribute("aria-busy", "true");
    expect(busy).toHaveClass("spinning");
    view.unmount();

    renderHeader(newClient());
    const idle = screen.getByRole("button", { name: "Refresh now" });
    expect(idle).toBeEnabled();
    expect(idle).not.toHaveClass("spinning");
  });

  it("marks the active tab and calls onTabChange when another tab is clicked", async () => {
    installFetchMock({ "/api/tasks": () => envelope([]) });
    const onTabChange = vi.fn();
    renderHeader(newClient(), { onTabChange });

    expect(screen.getByRole("link", { name: "Overview" })).toHaveClass("active");
    expect(screen.getByRole("link", { name: "Sessions" })).not.toHaveClass("active");
    expect(screen.getByRole("link", { name: "Kanban" })).not.toHaveClass("active");

    fireEvent.click(screen.getByRole("link", { name: "Sessions" }));
    expect(onTabChange).toHaveBeenCalledWith("sessions");

    fireEvent.click(screen.getByRole("link", { name: "Kanban" }));
    expect(onTabChange).toHaveBeenCalledWith("kanban");
  });

  it("shows the disconnected title on the status dot when not connected", async () => {
    installFetchMock({ "/api/tasks": () => envelope([]) });
    renderHeader(newClient(), { connected: false });

    expect(screen.getByTitle("Can't reach the local server")).toBeInTheDocument();
  });

  // F3: the mobile-collapse dropdown is CSS-hidden above 900px, not
  // React-unmounted - always in the DOM, so it's testable independent of
  // viewport width the same way the full-width `nav.app-tabs` already is.
  // With 3 tabs the dropdown now lists the 2 non-active ones, not a single
  // swap target.
  it("F3: the collapsed-nav dropdown is labeled with the active tab and lists the other tabs", async () => {
    installFetchMock({ "/api/tasks": () => envelope([]) });
    const onTabChange = vi.fn();
    renderHeader(newClient(), { activeTab: "sessions", onTabChange });

    expect(screen.getByTestId("nav-dropdown")).toHaveTextContent("Sessions");
    fireEvent.click(screen.getByTestId("nav-dropdown"));
    expect(screen.getByTestId("nav-dropdown-option-overview")).toBeInTheDocument();
    expect(screen.getByTestId("nav-dropdown-option-kanban")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("nav-dropdown-option-kanban"));
    expect(onTabChange).toHaveBeenCalledWith("kanban");
  });

  it("renders both the full and abbreviated wordmark suffix for CSS to switch between", async () => {
    installFetchMock({ "/api/tasks": () => envelope([]) });
    const { container } = renderHeader(newClient());

    expect(container.querySelector(".wordmark .sub")).toHaveTextContent("mission-control");
    expect(container.querySelector(".wordmark .sub-short")).toHaveTextContent("mc");
  });

  it("mounts the accent picker, independent of any project filter (AppHeader takes no project prop)", async () => {
    installFetchMock({ "/api/tasks": () => envelope([]) });
    renderHeader(newClient());

    expect(screen.getByTestId("accent-picker-btn")).toBeInTheDocument();
  });

  describe("attention signaling (PRD §6.9)", () => {
    it("shows no pill and the plain title when there's nothing to flag", async () => {
      installFetchMock({ "/api/tasks": () => envelope([task({ column: "planned", needs_attention: false })]) });
      renderHeader(newClient());

      await waitFor(() => expect(document.title).toBe(BASE_TITLE));
      expect(screen.queryByTestId("attention-pill")).not.toBeInTheDocument();
    });

    it("shows the pill and badges the title once Needs Attention cards exist, and clicking the pill navigates to Kanban", async () => {
      installFetchMock({
        "/api/tasks": () => envelope([task({ folder: "a" }), task({ folder: "b" })]),
      });
      const onTabChange = vi.fn();
      renderHeader(newClient(), { onTabChange });

      await waitFor(() => expect(screen.getByTestId("attention-pill")).toHaveTextContent("2 need attention"));
      expect(document.title).toBe("(2) Mission Control");

      fireEvent.click(screen.getByTestId("attention-pill"));
      expect(onTabChange).toHaveBeenCalledWith("kanban");
    });

    it("never chimes on page load, even when Needs Attention already has entries, but does chime once a new one arrives after being armed", async () => {
      const client = newClient();
      installFetchMock({ "/api/tasks": () => envelope([task({ folder: "a" })]) });
      renderHeader(client);
      await waitFor(() => expect(screen.getByTestId("attention-pill")).toHaveTextContent("1 need attention"));

      const playSpy = vi.spyOn(HTMLMediaElement.prototype, "play");
      // Arm the chime - browser autoplay policy blocks it until the user's
      // first click anywhere in the app (default: muted).
      fireEvent.click(screen.getByTestId("attention-mute-toggle"));
      fireEvent.click(screen.getByTestId("attention-mute-toggle")); // toggle back to unmuted

      act(() => {
        client.setQueryData(["tasks", "all"], [task({ folder: "a" }), task({ folder: "b" })]);
      });
      await waitFor(() => expect(screen.getByTestId("attention-pill")).toHaveTextContent("2 need attention"));
      expect(playSpy).toHaveBeenCalledTimes(1);

      // A repeat poll with the same set doesn't chime again.
      act(() => {
        client.setQueryData(["tasks", "all"], [task({ folder: "a" }), task({ folder: "b" })]);
      });
      await waitFor(() => expect(screen.getByTestId("attention-pill")).toHaveTextContent("2 need attention"));
      expect(playSpy).toHaveBeenCalledTimes(1);
    });

    it("stays muted-until-first-click by default: a new arrival before any click never chimes", async () => {
      const client = newClient();
      installFetchMock({ "/api/tasks": () => envelope([]) });
      renderHeader(client);
      await waitFor(() => expect(document.title).toBe(BASE_TITLE));

      const playSpy = vi.spyOn(HTMLMediaElement.prototype, "play");
      act(() => {
        client.setQueryData(["tasks", "all"], [task({ folder: "a" })]);
      });
      await waitFor(() => expect(screen.getByTestId("attention-pill")).toBeInTheDocument());
      expect(playSpy).not.toHaveBeenCalled();
    });

    it("the mute toggle persists across renders via localStorage", async () => {
      installFetchMock({ "/api/tasks": () => envelope([]) });
      renderHeader(newClient());

      expect(screen.getByTestId("attention-mute-toggle")).toHaveAttribute("title", "Mute attention chime");
      fireEvent.click(screen.getByTestId("attention-mute-toggle"));
      expect(screen.getByTestId("attention-mute-toggle")).toHaveAttribute("title", "Unmute attention chime");
      expect(localStorage.getItem("mc-attention-muted")).toBe("1");
    });
  });
});
