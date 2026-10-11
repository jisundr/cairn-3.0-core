import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";

// Every test gets its own QueryClient (no cross-test cache leakage) with
// retries off - the production default retries transient failures, which
// would make an induced-failure test slow and flaky rather than deterministic.
export function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    // `retry: false` covers most queries; a couple of hooks (useSessionTrace,
    // useCallDetails) set their own retry predicate that overrides this
    // default, so `retryDelay: 0` also collapses their backoff to
    // effectively instant, keeping every test's default wait timeout usable.
    defaultOptions: { queries: { retry: false, retryDelay: 0 }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}
