# Testing Patterns

**Analysis Date:** 2026-02-20

> **Note:** This project is in a pre-implementation state. No application source code or test files exist yet. These testing patterns are prescribed for adoption from project inception, based on the project type (cloud cost optimization SaaS with PostgreSQL backend, multi-cloud integrations, and ML components). All patterns below are required standards, not descriptions of existing code.

## Test Framework

**Runner:**
- Vitest (preferred) or Jest for TypeScript unit and integration tests
- Config: `vitest.config.ts` or `jest.config.ts` at project root

**Assertion Library:**
- Vitest built-in (`expect`) or Jest built-in (`expect`)

**Run Commands:**
```bash
npm run test              # Run all tests
npm run test:watch        # Watch mode
npm run test:coverage     # Run with coverage report
npm run test:e2e          # Run end-to-end tests (Playwright)
```

## Test File Organization

**Location:**
- Unit tests: co-located with source files as `{filename}.test.ts`
- Integration tests: `tests/integration/{feature}.integration.test.ts`
- E2E tests: `tests/e2e/{feature}.e2e.test.ts`

**Naming:**
- Test files: `{module-name}.test.ts` (e.g., `billing-data.service.test.ts`)
- Test functions: descriptive sentence format starting with `it('should ...')`

**Structure:**
```
src/
  services/
    billing-data.service.ts
    billing-data.service.test.ts
    cloud-provider.service.ts
    cloud-provider.service.test.ts
  controllers/
    budget.controller.ts
    budget.controller.test.ts
tests/
  integration/
    billing-sync.integration.test.ts
    optimization-rules.integration.test.ts
  e2e/
    cost-dashboard.e2e.test.ts
    budget-alerts.e2e.test.ts
  fixtures/
    cloud-provider.fixture.ts
    billing-data.fixture.ts
    resource.fixture.ts
```

## Test Structure

**Suite Organization:**
```typescript
// billing-data.service.test.ts
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { BillingDataService } from './billing-data.service';
import { createBillingDataFixture, createResourceFixture } from '@/tests/fixtures';

describe('BillingDataService', () => {
  let service: BillingDataService;

  beforeEach(() => {
    service = new BillingDataService({ db: mockDb, logger: mockLogger });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('getTenantCosts', () => {
    it('should return allocated costs for an active tenant', async () => {
      // arrange
      const tenant = { tenant_id: 'tenant-1', is_active: true };
      mockDb.tenantCosts.findByTenant.mockResolvedValue([createBillingDataFixture()]);

      // act
      const result = await service.getTenantCosts('tenant-1');

      // assert
      expect(result.allocated_cost).toBeGreaterThan(0);
      expect(result.resource_count).toBe(1);
    });

    it('should throw NotFoundError when tenant does not exist', async () => {
      mockDb.tenant.findById.mockResolvedValue(null);

      await expect(service.getTenantCosts('nonexistent')).rejects.toThrow('Tenant not found');
    });
  });
});
```

**Patterns:**
- Use Arrange-Act-Assert (AAA) structure, separated by blank lines within each test
- One logical assertion per `it` block — group related assertions only when they form a single concept
- Test names describe behavior, not implementation: `'should return 404 when resource not found'` not `'calls db.findById'`
- Use `describe` nesting to group by method/scenario (max 2 levels deep)

## Mocking

**Framework:** Vitest `vi.mock()` / Jest `jest.mock()`

**Database Mocking Pattern:**
```typescript
// Mock the database client, not the ORM internals
vi.mock('@/lib/db', () => ({
  db: {
    cloudProvider: {
      findById: vi.fn(),
      findAll: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
    },
    billingData: {
      findByResource: vi.fn(),
      findByDateRange: vi.fn(),
    },
  },
}));
```

**External API Mocking Pattern:**
```typescript
// Mock at the HTTP client level for cloud provider SDKs
vi.mock('@aws-sdk/client-cost-explorer', () => ({
  CostExplorerClient: vi.fn().mockImplementation(() => ({
    send: vi.fn(),
  })),
  GetCostAndUsageCommand: vi.fn(),
}));
```

**What to Mock:**
- All database calls in unit tests (never hit a real DB in unit tests)
- All external HTTP calls (AWS Cost Explorer, Azure Cost Management, GCP Billing)
- Email/notification senders
- Clock/time functions when testing scheduled reports or budget period calculations (`vi.useFakeTimers()`)
- ML model calls when testing the optimization rule evaluation logic

**What NOT to Mock:**
- Business logic being tested
- Pure utility functions (date formatting, cost calculations, percentage rounding)
- In-memory data structures
- In integration tests: the real database (use a test PostgreSQL instance instead)

## Fixtures and Factories

**Test Data Pattern:**
```typescript
// tests/fixtures/cloud-provider.fixture.ts
import type { CloudProvider } from '@/types';

export function createCloudProviderFixture(overrides?: Partial<CloudProvider>): CloudProvider {
  return {
    provider_id: 'aws',
    provider_name: 'Amazon Web Services',
    api_endpoint: 'https://ce.us-east-1.amazonaws.com',
    api_version: '2017-10-25',
    is_active: true,
    created_at: new Date('2026-01-01'),
    updated_at: new Date('2026-01-01'),
    ...overrides,
  };
}

export function createBillingDataFixture(overrides?: Partial<BillingData>): BillingData {
  return {
    billing_id: 'billing-001',
    resource_id: 'resource-001',
    billing_date: new Date('2026-02-01'),
    cost_amount: 125.50,
    currency_code: 'USD',
    usage_quantity: 720,
    usage_unit: 'Hrs',
    pricing_model: 'on-demand',
    discount_amount: 0,
    created_at: new Date('2026-02-01'),
    ...overrides,
  };
}
```

**Location:**
- All fixtures in `tests/fixtures/{entity-name}.fixture.ts`
- Export factory functions, never plain objects (allows per-test overrides)
- Include invalid-data factories for negative-case testing:
  ```typescript
  export function createInvalidBillingDataFixture(): Partial<BillingData> {
    return { cost_amount: -10, discount_amount: 50 }; // violates constraints
  }
  ```

## Coverage

**Requirements:**
- Minimum 80% line coverage for `src/services/`
- Minimum 70% line coverage for `src/controllers/`
- No coverage requirement on `src/types/` or `src/migrations/`
- Critical paths must have 100% branch coverage:
  - Budget alert threshold logic
  - Cost allocation percentage calculation
  - Optimization action approval/rejection flow
  - Compliance violation detection

**View Coverage:**
```bash
npm run test:coverage
# Report generated at: coverage/index.html
```

## Test Types

**Unit Tests:**
- Scope: Individual service methods, utility functions, validation logic
- Speed: Must run in < 5ms per test
- Database: Always mocked
- External APIs: Always mocked
- Target files: `src/services/*.ts`, `src/utils/*.ts`, `src/validators/*.ts`

**Integration Tests:**
- Scope: Full request→service→database round trips for key API endpoints
- Speed: Acceptable up to 2s per test
- Database: Real PostgreSQL test instance (seeded with fixtures before each suite)
- External APIs: Mocked at HTTP boundary
- Target files: `tests/integration/*.integration.test.ts`
- Setup: Use `beforeAll` to run migrations and seed, `afterAll` to teardown

**E2E Tests:**
- Framework: Playwright
- Scope: Critical user journeys through the UI:
  - Connect a cloud provider account
  - View cost dashboard and drill into resource costs
  - Create and activate a budget with alert thresholds
  - Review and approve an optimization recommendation
  - Generate and download a cost report
- Speed: Acceptable up to 30s per test
- Target files: `tests/e2e/*.e2e.test.ts`

## Common Patterns

**Async Testing:**
```typescript
// Always use async/await — never return raw Promises
it('should sync billing data from provider', async () => {
  const result = await billingService.syncFromProvider('aws', 'account-001');
  expect(result.records_synced).toBeGreaterThan(0);
});
```

**Error Testing:**
```typescript
// Test both the error type and the message
it('should throw ServiceError when provider API is unavailable', async () => {
  mockAwsClient.send.mockRejectedValue(new Error('Network timeout'));

  await expect(
    billingService.syncFromProvider('aws', 'account-001')
  ).rejects.toThrow(ServiceError);

  await expect(
    billingService.syncFromProvider('aws', 'account-001')
  ).rejects.toThrow('Failed to sync provider');
});
```

**Database Constraint Testing (Integration):**
```typescript
// Verify that CHECK constraints are enforced at the DB level
it('should reject billing records with negative cost amounts', async () => {
  await expect(
    db.billingData.create({
      ...createBillingDataFixture(),
      cost_amount: -5.00,
    })
  ).rejects.toThrow();
});
```

**Time-Dependent Testing:**
```typescript
// Always control time in tests that depend on dates or scheduling
it('should flag budget as exceeded when current spend surpasses threshold', () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-02-15'));

  const budget = createBudgetFixture({ period_start: '2026-02-01', period_end: '2026-02-28' });
  const result = budgetService.checkThreshold(budget, 950, 80); // 80% threshold

  expect(result.threshold_breached).toBe(true);
  vi.useRealTimers();
});
```

**Multi-Tenant Testing:**
- Always verify that data isolation is enforced across tenants in integration tests
- Use two distinct tenant fixtures in any test that touches `RESOURCE_TENANT_MAPPING`
- Verify that tenant A cannot access resources belonging to tenant B

---

*Testing analysis: 2026-02-20*
