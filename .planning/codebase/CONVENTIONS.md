# Coding Conventions

**Analysis Date:** 2026-02-20

> **Note:** This project is in a pre-implementation state. No application source code exists yet. These conventions are derived from the database schema (`context/ERD/ERD.sql`), project planning documents, and established best practices for the technology stack this project is intended to use. Conventions must be adopted from project inception.

## Naming Patterns

**Database Tables:**
- `SCREAMING_SNAKE_CASE` for all table names (e.g., `CLOUD_PROVIDER`, `BILLING_DATA`, `OPTIMIZATION_ACTION`)
- Reserved word avoidance: quote table name when conflicting with SQL keywords (e.g., `"USER"`)
- Join/mapping tables named as `{ENTITY_A}_{ENTITY_B}_MAPPING` (e.g., `RESOURCE_TENANT_MAPPING`)

**Database Columns:**
- `snake_case` for all column names (e.g., `provider_id`, `account_name`, `created_at`)
- Primary keys: `{table_singular}_id` (e.g., `provider_id`, `account_id`, `resource_id`)
- Foreign keys: same name as the primary key they reference (e.g., `provider_id` in `CLOUD_ACCOUNT` references `CLOUD_PROVIDER.provider_id`)
- Audit timestamps: always `created_at` and `updated_at` (not `createdAt`, `date_created`, etc.)
- Boolean flags: prefixed with `is_` (e.g., `is_active`, `is_automated`, `is_reservable`)

**Database Indexes:**
- `idx_{table}_{column}` for single-column indexes (e.g., `idx_billing_resource`, `idx_billing_date`)
- `idx_{table}_{col1}_{col2}` for composite indexes (e.g., `idx_billing_resource_date`)

**Database Constraints:**
- `chk_{table_or_column}` for CHECK constraints (e.g., `chk_resource_status`, `chk_pricing_model`)
- `fk_{table}_{relationship}` for named foreign key constraints (e.g., `fk_team_manager`)
- `trg_{table}_{event}` for triggers (e.g., `trg_cloud_provider_updated`)

**Database Views:**
- `v_{descriptive_name}` prefix for all views (e.g., `v_current_resource_costs`, `v_tenant_costs`)

**Application Files (to be established):**
- Use `kebab-case` for file names (e.g., `cloud-provider.service.ts`, `billing-data.controller.ts`)
- Use `PascalCase` for class/component names (e.g., `CloudProviderService`, `BillingDataController`)
- Use `camelCase` for functions and variables (e.g., `getTenantCosts`, `allocationPercent`)
- Use `SCREAMING_SNAKE_CASE` for constants (e.g., `MAX_RETRY_COUNT`, `DEFAULT_CURRENCY`)
- Use `PascalCase` for TypeScript interfaces and types (e.g., `CloudProvider`, `BillingRecord`)

## Code Style

**Formatting (to be configured):**
- Prettier for TypeScript/JavaScript formatting
- Target config: 2-space indentation, single quotes, trailing commas in multi-line structures, 100-char line width
- Config file: `.prettierrc` at project root

**Linting (to be configured):**
- ESLint with TypeScript plugin for application code
- `no-explicit-any` rule enforced — always provide typed interfaces
- Config file: `.eslintrc.json` or `eslint.config.js` at project root

**SQL Style:**
- SQL keywords in UPPERCASE (SELECT, INSERT, JOIN, WHERE, etc.)
- Table and column references in their defined case
- Each JOIN and WHERE clause on its own line
- CHECK constraints inline with column definitions where possible

## Import Organization

**Order (for TypeScript/JavaScript):**
1. Node.js built-in modules (`fs`, `path`, `crypto`)
2. Third-party packages (`express`, `prisma`, `aws-sdk`)
3. Internal absolute imports (`@/services/...`, `@/models/...`)
4. Relative imports (`./helpers`, `../utils`)

**Path Aliases (to be configured):**
- `@/` maps to `src/` for all internal imports
- Avoid deep relative paths (`../../../`) — use `@/` alias instead

## Error Handling

**Database Layer:**
- All database operations must use try/catch
- Re-throw errors with contextual information (table name, operation type, entity ID)
- Never swallow errors silently

**API Layer:**
- Use a centralized error handler middleware
- Return structured error responses: `{ error: string, code: string, details?: object }`
- Use appropriate HTTP status codes: 400 for validation, 401 for auth, 403 for authorization, 404 for not found, 500 for server errors

**Business Logic:**
- Use Result types or throw typed custom errors (not generic `Error`)
- Cloud provider API failures must be caught and surfaced as service-level errors, not crash the process

**Example pattern (to be implemented):**
```typescript
// services/cloud-provider.service.ts
async function syncProviderData(providerId: string): Promise<SyncResult> {
  try {
    const provider = await db.cloudProvider.findById(providerId);
    if (!provider) {
      throw new NotFoundError(`Cloud provider not found: ${providerId}`);
    }
    // ... sync logic
    return { success: true, recordsUpdated: count };
  } catch (error) {
    if (error instanceof NotFoundError) throw error;
    throw new ServiceError(`Failed to sync provider ${providerId}`, { cause: error });
  }
}
```

## Logging

**Framework:** Structured JSON logging (e.g., `pino` or `winston`)

**Patterns:**
- Log at `info` level for successful operations on significant entities
- Log at `warn` level for recoverable errors and validation failures
- Log at `error` level for unhandled exceptions and failed external API calls
- Always include `entity_type`, `entity_id`, and `action` fields in structured logs
- Never log sensitive data: `encrypted_credentials`, passwords, tokens, or PII

**Example:**
```typescript
logger.info({ entity_type: 'cloud_account', entity_id: accountId, action: 'sync_started' });
logger.error({ entity_type: 'billing_data', resource_id: resourceId, action: 'fetch_failed', error: err.message });
```

## Comments

**When to Comment:**
- Complex business logic (e.g., cost allocation calculations, ML model invocation)
- Non-obvious SQL queries or index choices
- Workarounds for external API limitations (cite the limitation)
- Security-sensitive code paths

**JSDoc/TSDoc:**
- Required on all public service methods and API controllers
- Include `@param`, `@returns`, and `@throws` for methods with non-trivial signatures
- Not required on private helper functions with self-explanatory names

**SQL:**
- Comment each table's purpose above its CREATE TABLE statement
- Explain composite index rationale inline (e.g., `-- Supports tenant cost attribution queries`)

## Function Design

**Size:** Functions should do one thing. If a function exceeds ~40 lines, extract helpers.

**Parameters:**
- Use named parameter objects for 3+ arguments: `function createBudget(params: CreateBudgetParams)`
- Avoid boolean flag parameters — use enums or separate functions instead

**Return Values:**
- Async functions always return typed Promises
- Never return `undefined` where `null` is the intended empty signal
- Prefer explicit return types on all exported functions

## Module Design

**Exports:**
- Named exports preferred over default exports for services and utilities
- Default export only for framework entry points (e.g., Express app, Next.js pages)

**Barrel Files:**
- Use `index.ts` barrel files within each feature directory to aggregate exports
- Do not create a single root-level barrel that re-exports everything (causes circular dependency risk)

## Data Validation

**Input Validation:**
- Validate all API inputs at the controller/route level before passing to service layer
- Use a schema validation library (e.g., `zod`) with types inferred from schemas
- Enforce database CHECK constraint values in application-level enums:
  - Resource status: `'provisioning' | 'active' | 'stopped' | 'terminated'`
  - Pricing model: `'on-demand' | 'reserved' | 'spot' | 'savings-plan'`
  - Alert severity: `'info' | 'warning' | 'critical'`
  - User roles: `'admin' | 'devops' | 'finance' | 'auditor' | 'viewer'`

## Sensitive Data

**Security rules:**
- `encrypted_credentials` in `CLOUD_ACCOUNT` must always be encrypted at rest — never store plaintext
- Never log or expose `encrypted_credentials`, API keys, or tokens in responses
- Audit log (`AUDIT_LOG`) must record `before_state` and `after_state` for all mutations to sensitive tables
- `ip_address` and `user_agent` collection required in audit logs for compliance

---

*Convention analysis: 2026-02-20*
