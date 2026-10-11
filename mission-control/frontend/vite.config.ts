import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// No Tailwind plugin here (unlike token-metering/frontend) - this build
// ports design.css literally rather than reinterpreting it as utility
// classes. outDir points at ../static (mirroring token-metering/frontend's
// own vite.config.ts) so server.py's existing static_dir route
// (STATIC_DIR_NAME) serves the real compiled frontend instead of its
// not-built-yet placeholder.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../static",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    // jsdom's default test URL is "about:blank", an opaque origin that
    // throws on any `localStorage` access at all (Storage API requires a
    // real origin) - the attention-signaling mute toggle (PRD §6.9) is this
    // app's first use of it, so tests need a concrete origin the way the
    // real app already has one (served from `http://localhost:<port>`).
    environmentOptions: { jsdom: { url: "http://localhost/" } },
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
    // Vitest's default excludes don't cover e2e/ - without this it also
    // tries (and fails) to collect the Playwright specs there, which use
    // their own `test()`/`test.describe()` from @playwright/test.
    exclude: ["e2e/**", "node_modules/**"],
  },
});
