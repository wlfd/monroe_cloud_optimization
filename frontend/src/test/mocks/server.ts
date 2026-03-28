import { setupServer } from "msw/node";
import { handlers } from "./handlers";

// Create the MSW server instance with all default handlers.
// Individual tests can override specific handlers with server.use(...)
// and then call server.resetHandlers() in afterEach to restore defaults.
export const server = setupServer(...handlers);
