"""
Tenant seed script — creates 6 fictional customer tenants with realistic billing data,
display names, and attribution rows for the prior and current billing months.

Run with:
  docker compose exec api python -m app.scripts.seed_tenants

Appends tenant-tagged billing records alongside existing data. Safe to re-run (upserts throughout).
Does NOT clear existing billing_records.
"""
import asyncio
import random
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import AsyncSessionLocal
from app.models.attribution import TenantAttribution, TenantProfile
from app.models.billing import BillingRecord
from app.services.attribution import run_attribution

# ---------------------------------------------------------------------------
# Cost pattern helper (mirrors seed_billing.py)
# ---------------------------------------------------------------------------

def _daily_cost(base: float, pattern: str, day: date) -> float:
    is_weekend = day.weekday() >= 5
    if pattern == "flat":
        return round(base * (1 + random.uniform(-0.05, 0.05)), 6)
    if pattern == "dev_idle":
        return round(base * (1 + random.uniform(-0.03, 0.03)), 6)
    if pattern == "workday":
        factor = 0.25 if is_weekend else 1.0
        return round(base * factor * (1 + random.uniform(-0.08, 0.08)), 6)
    if pattern == "storage":
        return round(base * (1 + random.uniform(-0.02, 0.02)), 6)
    return round(base * (1 + random.uniform(-0.10, 0.10)), 6)


# ---------------------------------------------------------------------------
# Tenant definitions
# Each entry: tenant_id, display_name, subscription_id, resources[]
# Each resource: (resource_group, service_name, meter_category, region,
#                 resource_id_suffix, resource_name, base_daily_cost, pattern)
# ---------------------------------------------------------------------------

# fmt: off
TENANTS = [
    {
        "tenant_id": "tenant-acme",
        "display_name": "Acme Corp",
        "subscription_id": "sub-acme-0001",
        "resources": [
            # Large enterprise — heavy VMs + SQL + AKS, strong Reserved Instance candidates
            ("acme-prod-rg",   "Virtual Machines",          "Compute",   "eastus",
             "resourceGroups/acme-prod-rg/providers/Microsoft.Compute/virtualMachines/acme-app-server-01",
             "acme-app-server-01",  22.00, "flat"),
            ("acme-prod-rg",   "Azure SQL Database",        "Databases", "eastus",
             "resourceGroups/acme-prod-rg/providers/Microsoft.Sql/servers/acme/databases/acme-prod-db",
             "acme-prod-db",        28.00, "flat"),
            ("acme-prod-rg",   "Azure Kubernetes Service",  "Compute",   "eastus",
             "resourceGroups/acme-prod-rg/providers/Microsoft.ContainerService/managedClusters/acme-aks",
             "acme-aks-cluster",    35.00, "flat"),
            ("acme-dev-rg",    "Virtual Machines",          "Compute",   "eastus",
             "resourceGroups/acme-dev-rg/providers/Microsoft.Compute/virtualMachines/acme-dev-vm",
             "acme-dev-vm",          8.00, "dev_idle"),
            ("acme-shared-rg", "Azure Storage",             "Storage",   "eastus",
             "resourceGroups/acme-shared-rg/providers/Microsoft.Storage/storageAccounts/acmedataarchive",
             "acme-data-archive",   12.00, "storage"),
        ],
    },
    {
        "tenant_id": "tenant-stellar",
        "display_name": "Stellar Labs",
        "subscription_id": "sub-stellar-0002",
        "resources": [
            # Tech startup — Kubernetes-heavy, weekday workloads
            ("stellar-compute-rg", "Azure Kubernetes Service", "Compute",   "westus2",
             "resourceGroups/stellar-compute-rg/providers/Microsoft.ContainerService/managedClusters/stellar-k8s",
             "stellar-k8s",           30.00, "workday"),
            ("stellar-compute-rg", "Azure Functions",          "Compute",   "westus2",
             "resourceGroups/stellar-compute-rg/providers/Microsoft.Web/sites/stellar-api-functions",
             "stellar-api-functions",  4.50, "flat"),
            ("stellar-data-rg",    "Azure SQL Database",       "Databases", "westus2",
             "resourceGroups/stellar-data-rg/providers/Microsoft.Sql/servers/stellar/databases/stellar-analytics-db",
             "stellar-analytics-db",  18.00, "flat"),
            ("stellar-data-rg",    "Azure Storage",            "Storage",   "westus2",
             "resourceGroups/stellar-data-rg/providers/Microsoft.Storage/storageAccounts/stellarartifacts",
             "stellar-artifacts",      5.00, "storage"),
        ],
    },
    {
        "tenant_id": "tenant-nova",
        "display_name": "Nova Digital",
        "subscription_id": "sub-nova-0003",
        "resources": [
            # Media company — CDN + Storage dominant, render VMs on weekdays
            ("nova-cdn-rg",     "Azure CDN",     "Networking",  "centralus",
             "resourceGroups/nova-cdn-rg/providers/Microsoft.Cdn/profiles/nova-media-cdn",
             "nova-media-cdn",    14.00, "flat"),
            ("nova-storage-rg", "Azure Storage", "Storage",     "centralus",
             "resourceGroups/nova-storage-rg/providers/Microsoft.Storage/storageAccounts/novamediaassets",
             "nova-media-assets", 20.00, "storage"),
            ("nova-compute-rg", "Virtual Machines", "Compute",  "centralus",
             "resourceGroups/nova-compute-rg/providers/Microsoft.Compute/virtualMachines/nova-render-vm",
             "nova-render-vm",    12.00, "workday"),
            ("nova-compute-rg", "Azure Monitor", "Management",  "centralus",
             "resourceGroups/nova-compute-rg/providers/Microsoft.Insights/components/nova-app-insights",
             "nova-app-insights",  2.50, "flat"),
        ],
    },
    {
        "tenant_id": "tenant-apex",
        "display_name": "Apex Retail",
        "subscription_id": "sub-apex-0004",
        "resources": [
            # Retail — always-on storefront SQL, batch order processing on weekdays
            ("apex-prod-rg",   "Virtual Machines",   "Compute",   "eastus2",
             "resourceGroups/apex-prod-rg/providers/Microsoft.Compute/virtualMachines/apex-web-server",
             "apex-web-server",       16.00, "flat"),
            ("apex-prod-rg",   "Azure SQL Database", "Databases", "eastus2",
             "resourceGroups/apex-prod-rg/providers/Microsoft.Sql/servers/apex/databases/apex-inventory-db",
             "apex-inventory-db",     32.00, "flat"),
            ("apex-batch-rg",  "Virtual Machines",   "Compute",   "eastus2",
             "resourceGroups/apex-batch-rg/providers/Microsoft.Compute/virtualMachines/apex-batch-vm",
             "apex-batch-vm",         10.00, "workday"),
            ("apex-shared-rg", "Azure CDN",          "Networking","eastus2",
             "resourceGroups/apex-shared-rg/providers/Microsoft.Cdn/profiles/apex-storefront-cdn",
             "apex-storefront-cdn",    6.00, "flat"),
        ],
    },
    {
        "tenant_id": "tenant-cerulean",
        "display_name": "Cerulean Health",
        "subscription_id": "sub-cerulean-0005",
        "resources": [
            # Healthcare — compliance-heavy SQL + Storage, always-on app VMs
            ("cerulean-hipaa-rg", "Azure SQL Database", "Databases", "eastus",
             "resourceGroups/cerulean-hipaa-rg/providers/Microsoft.Sql/servers/cerulean/databases/cerulean-patient-db",
             "cerulean-patient-db", 38.00, "flat"),
            ("cerulean-hipaa-rg", "Azure Storage",      "Storage",   "eastus",
             "resourceGroups/cerulean-hipaa-rg/providers/Microsoft.Storage/storageAccounts/ceruleanbackups",
             "cerulean-backups",    15.00, "storage"),
            ("cerulean-app-rg",   "Virtual Machines",   "Compute",   "eastus",
             "resourceGroups/cerulean-app-rg/providers/Microsoft.Compute/virtualMachines/cerulean-app-vm",
             "cerulean-app-vm",     14.00, "flat"),
            ("cerulean-app-rg",   "Azure Monitor",      "Management","eastus",
             "resourceGroups/cerulean-app-rg/providers/Microsoft.Insights/components/cerulean-insights",
             "cerulean-insights",    3.00, "flat"),
        ],
    },
    {
        "tenant_id": "tenant-ironworks",
        "display_name": "Ironworks Inc",
        "subscription_id": "sub-ironworks-0006",
        "resources": [
            # Manufacturing — batch processing VMs on weekdays, flat SQL + Storage
            ("ironworks-compute-rg", "Virtual Machines",   "Compute",   "northeurope",
             "resourceGroups/ironworks-compute-rg/providers/Microsoft.Compute/virtualMachines/ironworks-batch-01",
             "ironworks-batch-01", 12.00, "workday"),
            ("ironworks-compute-rg", "Azure SQL Database", "Databases", "northeurope",
             "resourceGroups/ironworks-compute-rg/providers/Microsoft.Sql/servers/ironworks/databases/ironworks-ops-db",
             "ironworks-ops-db",   14.00, "flat"),
            ("ironworks-storage-rg", "Azure Storage",      "Storage",   "northeurope",
             "resourceGroups/ironworks-storage-rg/providers/Microsoft.Storage/storageAccounts/ironworksarchive",
             "ironworks-archive",   7.00, "storage"),
        ],
    },
]
# fmt: on


# ---------------------------------------------------------------------------
# Prior-month attribution seeder
# ---------------------------------------------------------------------------

async def _seed_prior_month_attribution(year: int, month: int) -> None:
    """Aggregate tagged billing records for year/month and upsert TenantAttribution rows.

    Runs before run_attribution() so MoM delta is populated on the current month.
    """
    async with AsyncSessionLocal() as db:
        tagged_stmt = (
            select(BillingRecord.tag, func.sum(BillingRecord.pre_tax_cost).label("total"))
            .where(
                BillingRecord.tag != "",
                func.extract("year", BillingRecord.usage_date) == year,
                func.extract("month", BillingRecord.usage_date) == month,
            )
            .group_by(BillingRecord.tag)
        )
        tagged_rows = (await db.execute(tagged_stmt)).all()
        tagged_costs: dict[str, Decimal] = {row.tag: Decimal(str(row.total)) for row in tagged_rows}

        if not tagged_costs:
            print(f"  No tagged billing data for {year}-{month:02d} — skipping prior month attribution.")
            return

        grand_total = sum(float(v) for v in tagged_costs.values())
        computed_at = datetime.now(UTC)

        for tenant_id, tagged_cost in tagged_costs.items():
            total_cost = float(tagged_cost)
            pct = (total_cost / grand_total * 100) if grand_total > 0 else 0.0

            top_svc_stmt = (
                select(
                    BillingRecord.service_name,
                    func.sum(BillingRecord.pre_tax_cost).label("svc_cost"),
                )
                .where(
                    BillingRecord.tag == tenant_id,
                    func.extract("year", BillingRecord.usage_date) == year,
                    func.extract("month", BillingRecord.usage_date) == month,
                )
                .group_by(BillingRecord.service_name)
                .order_by(func.sum(BillingRecord.pre_tax_cost).desc())
                .limit(1)
            )
            top_row = (await db.execute(top_svc_stmt)).first()

            upsert = pg_insert(TenantAttribution).values(
                tenant_id=tenant_id,
                year=year,
                month=month,
                total_cost=total_cost,
                pct_of_total=round(pct, 4),
                mom_delta_usd=None,
                top_service_category=top_row.service_name if top_row else None,
                allocated_cost=0.0,
                tagged_cost=total_cost,
                computed_at=computed_at,
                updated_at=computed_at,
            )
            upsert = upsert.on_conflict_do_update(
                index_elements=["tenant_id", "year", "month"],
                set_={
                    "total_cost": upsert.excluded.total_cost,
                    "pct_of_total": upsert.excluded.pct_of_total,
                    "top_service_category": upsert.excluded.top_service_category,
                    "tagged_cost": upsert.excluded.tagged_cost,
                    "computed_at": upsert.excluded.computed_at,
                    "updated_at": upsert.excluded.updated_at,
                },
            )
            await db.execute(upsert)

        await db.commit()
        print(f"  Upserted {len(tagged_costs)} attribution rows for {year}-{month:02d}.")


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

async def seed() -> None:
    today = date.today()
    start = today - timedelta(days=89)  # 90 days inclusive, matching seed_billing.py

    # ── Step 1: Insert tenant-tagged billing records ──────────────────────
    records_to_insert = []
    current = start
    while current <= today:
        for tenant in TENANTS:
            for (rg, svc, meter, region, rid, rname, base, pattern) in tenant["resources"]:
                records_to_insert.append({
                    "usage_date": current,
                    "subscription_id": tenant["subscription_id"],
                    "resource_group": rg,
                    "service_name": svc,
                    "meter_category": meter,
                    "pre_tax_cost": _daily_cost(base, pattern, current),
                    "currency": "USD",
                    "region": region,
                    "tag": tenant["tenant_id"],
                    "resource_id": f"/subscriptions/{tenant['subscription_id']}/{rid}",
                    "resource_name": rname,
                })
        current += timedelta(days=1)

    total_resources = sum(len(t["resources"]) for t in TENANTS)
    print(f"Generating billing records: {len(TENANTS)} tenants × {total_resources} resources × 90 days …")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            pg_insert(BillingRecord)
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
        print(f"  Inserted {result.rowcount} billing records.")

    # ── Step 2: Upsert TenantProfile rows with display names ─────────────
    print("Upserting tenant profiles …")
    async with AsyncSessionLocal() as db:
        for tenant in TENANTS:
            upsert = pg_insert(TenantProfile).values(
                tenant_id=tenant["tenant_id"],
                display_name=tenant["display_name"],
                is_new=False,
                first_seen=start,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            upsert = upsert.on_conflict_do_update(
                index_elements=["tenant_id"],
                set_={
                    "display_name": upsert.excluded.display_name,
                    "updated_at": upsert.excluded.updated_at,
                },
            )
            await db.execute(upsert)
        await db.commit()
        print(f"  Upserted {len(TENANTS)} tenant profiles.")

    # ── Step 3: Seed prior month attribution so MoM delta shows up ───────
    prior_year = today.year if today.month > 1 else today.year - 1
    prior_month = today.month - 1 if today.month > 1 else 12
    print(f"Seeding prior month attribution ({prior_year}-{prior_month:02d}) …")
    await _seed_prior_month_attribution(prior_year, prior_month)

    # ── Step 4: Compute current month attribution via service ─────────────
    print(f"Running attribution for current month ({today.year}-{today.month:02d}) …")
    await run_attribution()
    print("  Done.")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\nTenants seeded (approx monthly spend):")
    for tenant in TENANTS:
        avg_monthly = 0.0
        for (_, _, _, _, _, _, base, pattern) in tenant["resources"]:
            avg_factor = 0.79 if pattern == "workday" else 1.0
            avg_monthly += base * avg_factor * 30
        print(f"  {tenant['display_name']:<20} ({tenant['tenant_id']})  ~${avg_monthly:,.0f}/mo")


if __name__ == "__main__":
    asyncio.run(seed())
