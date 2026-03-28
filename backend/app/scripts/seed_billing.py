"""
Billing seed script — generates 90 days of synthetic billing data with
realistic cost patterns designed to produce meaningful LLM recommendations.

Run with:
  docker compose exec api python -m app.scripts.seed_billing

Clears existing billing_records and inserts fresh data on each run.

Cost patterns (each signals a different recommendation category):
  flat      — consistent 7 days ±5% noise  → Reserved Instance candidates
  dev_idle  — consistent 7 days (dev env that runs through weekends) → idle/auto-shutdown
  workday   — high Mon-Fri, ~25% on weekends → right-sizing/scheduling opportunity
  storage   — very flat ±2%, 7 days → lifecycle management candidates
"""

import asyncio
import random
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.core.database import AsyncSessionLocal
from app.models.billing import BillingRecord

SUBSCRIPTION_ID = "mock-subscription-id"

# fmt: off
# Each entry: (resource_group, service_name, meter_category, region, resource_id_suffix, resource_name, base_daily_cost, pattern)
#
# NOTE: The billing table enforces unique(usage_date, subscription_id, resource_group,
# service_name, meter_category) — so each resource must be in a distinct combination.
# Resources are spread across dedicated resource groups to avoid collisions.
RESOURCES = [
    # ── Production web tier ─────────────────────────────────────────────────
    # Always-on VM, very flat spend → strong Reserved Instance candidate
    (
        "web-rg",
        "Virtual Machines", "Compute", "eastus",
        "resourceGroups/web-rg/providers/Microsoft.Compute/virtualMachines/prod-vm-web-frontend",
        "prod-vm-web-frontend", 18.50, "flat",
    ),

    # ── Production API tier ─────────────────────────────────────────────────
    # Always-on VM, very flat spend → Reserved Instance candidate
    (
        "api-rg",
        "Virtual Machines", "Compute", "eastus",
        "resourceGroups/api-rg/providers/Microsoft.Compute/virtualMachines/prod-vm-api-server",
        "prod-vm-api-server", 14.20, "flat",
    ),

    # ── Production data tier ────────────────────────────────────────────────
    # SQL database — consistent, high cost → Reserved Instance or right-sizing candidate
    (
        "data-rg",
        "Azure SQL Database", "Databases", "eastus",
        "resourceGroups/data-rg/providers/Microsoft.Sql/servers/prod-sql/databases/prod-sql-app-db",
        "prod-sql-app-db", 22.00, "flat",
    ),

    # AKS cluster — large, consistent workload → strongest Reserved Instance candidate
    (
        "data-rg",
        "Azure Kubernetes Service", "Compute", "eastus",
        "resourceGroups/data-rg/providers/Microsoft.ContainerService/managedClusters/prod-aks-data-cluster",
        "prod-aks-data-cluster", 31.00, "flat",
    ),

    # Production backup archive — flat accumulating storage cost → lifecycle policy candidate
    (
        "data-rg",
        "Azure Storage", "Storage", "eastus",
        "resourceGroups/data-rg/providers/Microsoft.Storage/storageAccounts/prodbackuparchive",
        "prod-backup-archive", 4.80, "storage",
    ),

    # ── Batch / processing tier ─────────────────────────────────────────────
    # Batch processor — high weekdays, near-zero weekends → scheduling or right-sizing opportunity
    (
        "batch-rg",
        "Virtual Machines", "Compute", "eastus",
        "resourceGroups/batch-rg/providers/Microsoft.Compute/virtualMachines/prod-vm-batch-processor",
        "prod-vm-batch-processor", 16.00, "workday",
    ),

    # ── Development environment ─────────────────────────────────────────────
    # Dev CI/CD build agent — always-on including weekends (it shouldn't be) → idle candidate
    (
        "dev-rg",
        "Virtual Machines", "Compute", "westus2",
        "resourceGroups/dev-rg/providers/Microsoft.Compute/virtualMachines/dev-vm-build-agent",
        "dev-vm-build-agent", 6.40, "dev_idle",
    ),

    # Old dev build artifacts accumulating in storage → lifecycle management / deletion candidate
    (
        "dev-rg",
        "Azure Storage", "Storage", "westus2",
        "resourceGroups/dev-rg/providers/Microsoft.Storage/storageAccounts/devoldartifacts",
        "dev-old-artifacts", 2.50, "storage",
    ),

    # Dev ETL function — low cost, mostly idle (below $50/mo threshold, informational only)
    (
        "dev-rg",
        "Azure Functions", "Compute", "westus2",
        "resourceGroups/dev-rg/providers/Microsoft.Web/sites/dev-func-etl-processor",
        "dev-func-etl-processor", 0.90, "flat",
    ),

    # ── Shared services ─────────────────────────────────────────────────────
    (
        "shared-rg",
        "Azure CDN", "Networking", "centralus",
        "resourceGroups/shared-rg/providers/Microsoft.Cdn/profiles/global-cdn-profile",
        "global-cdn-profile", 3.50, "flat",
    ),
    (
        "shared-rg",
        "Azure Monitor", "Management", "centralus",
        "resourceGroups/shared-rg/providers/Microsoft.Insights/components/prod-app-insights",
        "prod-app-insights", 2.10, "flat",
    ),
]
# fmt: on


def _daily_cost(base: float, pattern: str, day: date) -> float:
    """Compute daily cost based on pattern and day-of-week."""
    is_weekend = day.weekday() >= 5  # Saturday=5, Sunday=6

    if pattern == "flat":
        # Consistent 7 days — always-on production workload
        # Tight noise so the flatness is obvious to the LLM
        return round(base * (1 + random.uniform(-0.05, 0.05)), 6)

    if pattern == "dev_idle":
        # Same cost on weekdays AND weekends — the problem signal
        # A dev VM shouldn't cost the same on Sunday as Monday
        return round(base * (1 + random.uniform(-0.03, 0.03)), 6)

    if pattern == "workday":
        # High Mon-Fri, drops to ~25% on weekends
        # Clear signal: resource is only used during business hours
        factor = 0.25 if is_weekend else 1.0
        return round(base * factor * (1 + random.uniform(-0.08, 0.08)), 6)

    if pattern == "storage":
        # Very flat — storage just accumulates regardless of day
        return round(base * (1 + random.uniform(-0.02, 0.02)), 6)

    return round(base * (1 + random.uniform(-0.10, 0.10)), 6)


async def seed() -> None:
    today = date.today()
    start = today - timedelta(days=89)  # 90 days inclusive

    records_to_insert = []
    current = start
    while current <= today:
        for rg, svc, meter, region, rid_suffix, rname, base_cost, pattern in RESOURCES:
            records_to_insert.append(
                {
                    "usage_date": current,
                    "subscription_id": SUBSCRIPTION_ID,
                    "resource_group": rg,
                    "service_name": svc,
                    "meter_category": meter,
                    "pre_tax_cost": _daily_cost(base_cost, pattern, current),
                    "currency": "USD",
                    "region": region,
                    "tag": "",
                    "resource_id": f"/subscriptions/{SUBSCRIPTION_ID}/{rid_suffix}",
                    "resource_name": rname,
                }
            )
        current += timedelta(days=1)

    async with AsyncSessionLocal() as db:
        await db.execute(text("DELETE FROM billing_records"))
        await db.commit()
        print("Cleared existing billing_records.")

        result = await db.execute(
            insert(BillingRecord)
            .values(records_to_insert)
            .on_conflict_do_nothing(
                index_elements=[
                    "usage_date",
                    "subscription_id",
                    "resource_group",
                    "service_name",
                    "meter_category",
                ]
            )
        )
        await db.commit()
        print(
            f"Inserted {result.rowcount} billing records ({len(RESOURCES)} resources × 90 days).\n"
        )

    # Summary of what qualifies for LLM recommendations ($50/mo threshold)
    print("Resources seeded (approx monthly spend, sorted desc):")
    qualifying = []
    for rg, _, _, _, _, rname, base, pattern in RESOURCES:
        # workday pattern averages ~(5 + 2*0.25)/7 ≈ 79% of base
        avg_factor = 0.79 if pattern == "workday" else 1.0
        monthly = base * avg_factor * 30
        qualifies = monthly >= 50.0
        qualifying.append((monthly, rname, rg, pattern, qualifies))

    for monthly, rname, rg, pattern, qualifies in sorted(qualifying, reverse=True):
        marker = "✓" if qualifies else "✗ (below $50 threshold)"
        print(f"  ${monthly:>7.0f}/mo  [{pattern:9s}]  {rname} ({rg})  {marker}")


if __name__ == "__main__":
    asyncio.run(seed())
