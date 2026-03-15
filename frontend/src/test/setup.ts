import '@testing-library/jest-dom';
import { server } from './mocks/server';

// Start the MSW server before all tests. Requests that have no matching
// handler will throw an error so tests fail loudly instead of silently
// passing with empty data.
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));

// Reset any runtime handler overrides added via server.use() inside individual
// tests so later tests always start with the default handler set.
afterEach(() => server.resetHandlers());

// Clean up the server when the test suite finishes.
afterAll(() => server.close());
