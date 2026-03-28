import '@testing-library/jest-dom';
import { server } from './mocks/server';

// ResizeObserver is used by Recharts (ResponsiveContainer) but is not
// implemented in jsdom. Provide a no-op stub so chart tests don't crash.
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Pointer-capture APIs are used by @testing-library/user-event and Radix UI
// but are not implemented in jsdom. Stub them so pointer-event-driven tests
// don't throw unhandled "hasPointerCapture is not a function" errors.
if (!window.HTMLElement.prototype.hasPointerCapture) {
  window.HTMLElement.prototype.hasPointerCapture = () => false;
  window.HTMLElement.prototype.setPointerCapture = () => {};
  window.HTMLElement.prototype.releasePointerCapture = () => {};
}

// Start the MSW server before all tests. Requests that have no matching
// handler will throw an error so tests fail loudly instead of silently
// passing with empty data.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));

// Reset any runtime handler overrides added via server.use() inside individual
// tests so later tests always start with the default handler set.
afterEach(() => server.resetHandlers());

// Clean up the server when the test suite finishes.
afterAll(() => server.close());
