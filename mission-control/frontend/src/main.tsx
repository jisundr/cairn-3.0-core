import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App.tsx";
import { applyAccentTheme, getStoredAccentTheme } from "./lib/theme";
import "./styles/design.css";

// Applied before the first render (not inside AccentPicker's own mount
// effect) so a hard reload shows the persisted per-install accent
// immediately, rather than flashing the default green for a frame.
applyAccentTheme(getStoredAccentTheme());

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
