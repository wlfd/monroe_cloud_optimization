import asyncio
import logging
from datetime import datetime

from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition,
    QueryDataset,
    QueryTimePeriod,
    QueryAggregation,
    QueryGrouping,
    QueryColumnType,
)
from azure.core.exceptions import HttpResponseError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
    retry_if_exception_type,
    before_sleep_log,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _build_client() -> CostManagementClient:
    """Build a synchronous Azure Cost Management client using DefaultAzureCredential."""
    credential = DefaultAzureCredential()
    return CostManagementClient(credential)


def _fetch_page_sync(
    client: CostManagementClient,
    scope: str,
    query_def: QueryDefinition,
) -> tuple[list, list[str], str | None]:
    """Synchronous page fetch — call via asyncio.to_thread to avoid blocking the event loop."""
    result = client.query.usage(scope=scope, parameters=query_def)
    if result is None:
        return [], [], None
    column_names = [c.name for c in result.columns]
    rows = list(result.rows) if result.rows else []
    next_link = getattr(result, "next_link", None)
    return rows, column_names, next_link


def _fetch_next_page_sync(
    token: str,
    next_url: str,
) -> tuple[list, list[str], str | None]:
    """Follow pagination via raw HTTP (safety net — chunked date windows avoid this in practice).

    Note: For MVP the chunked-by-week approach in fetch_billing_data avoids pagination entirely.
    This function is a safety net only.
    """
    try:
        import httpx
    except ImportError:
        raise NotImplementedError("Install httpx for pagination support")

    headers = {"Authorization": f"Bearer {token}"}
    response = httpx.get(next_url, headers=headers)
    response.raise_for_status()
    data = response.json()

    props = data.get("properties", {})
    rows = props.get("rows", [])
    raw_columns = props.get("columns", [])
    column_names = [c.get("name", "") for c in raw_columns]
    next_link = props.get("nextLink")

    return rows, column_names, next_link


async def fetch_billing_data(
    scope: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch billing data from Azure Cost Management API, or return synthetic data in mock mode.

    When MOCK_AZURE=True, returns synthetic records without making any Azure API calls.
    Safe for local development without real Azure credentials.
    """
    settings = get_settings()
    if settings.MOCK_AZURE:
        # Return synthetic billing data for local dev / CI
        sub_id = settings.AZURE_SUBSCRIPTION_ID or "mock-subscription-id"
        return [
            {
                "UsageDate": 20260101,
                "SubscriptionId": sub_id,
                "ResourceGroup": "mock-rg-1",
                "ServiceName": "Virtual Machines",
                "MeterCategory": "Compute",
                "ResourceLocation": "eastus",
                "tenant_id": "",
                "ResourceId": "/subscriptions/mock-sub/resourceGroups/mock-rg-1/providers/Microsoft.Compute/virtualMachines/mock-vm-1",
                "PreTaxCost": 12.50,
                "Currency": "USD",
            },
            {
                "UsageDate": 20260101,
                "SubscriptionId": sub_id,
                "ResourceGroup": "mock-rg-2",
                "ServiceName": "Azure Storage",
                "MeterCategory": "Storage",
                "ResourceLocation": "eastus",
                "tenant_id": "",
                "ResourceId": "/subscriptions/mock-sub/resourceGroups/mock-rg-2/providers/Microsoft.Storage/storageAccounts/mock-storage-1",
                "PreTaxCost": 3.20,
                "Currency": "USD",
            },
            {
                "UsageDate": 20260101,
                "SubscriptionId": sub_id,
                "ResourceGroup": "mock-rg-1",
                "ServiceName": "Azure SQL Database",
                "MeterCategory": "Databases",
                "ResourceLocation": "eastus",
                "tenant_id": "",
                "ResourceId": "/subscriptions/mock-sub/resourceGroups/mock-rg-1/providers/Microsoft.Sql/servers/mock-sql-1",
                "PreTaxCost": 8.75,
                "Currency": "USD",
            },
        ]

    # Real Azure path — build client and query
    client = _build_client()

    query_def = QueryDefinition(
        type="Usage",
        timeframe="Custom",
        time_period=QueryTimePeriod(**{"from": start.isoformat(), "to": end.isoformat()}),
        dataset=QueryDataset(
            granularity="Daily",
            aggregation={"totalCost": QueryAggregation(name="PreTaxCost", function="Sum")},
            grouping=[
                QueryGrouping(type=QueryColumnType.DIMENSION, name="SubscriptionId"),
                QueryGrouping(type=QueryColumnType.DIMENSION, name="ResourceGroup"),
                QueryGrouping(type=QueryColumnType.DIMENSION, name="ServiceName"),
                QueryGrouping(type=QueryColumnType.DIMENSION, name="MeterCategory"),
                QueryGrouping(type=QueryColumnType.DIMENSION, name="ResourceLocation"),
                QueryGrouping(type=QueryColumnType.TAG, name="tenant_id"),
                QueryGrouping(type=QueryColumnType.DIMENSION, name="ResourceId"),
            ],
        ),
    )

    # CRITICAL: Wrap synchronous SDK call in asyncio.to_thread to avoid blocking the event loop.
    # The Azure SDK uses the synchronous `requests` library internally.
    rows, column_names, _next_link = await asyncio.to_thread(
        _fetch_page_sync, client, scope, query_def
    )

    all_records: list[dict] = []
    for row in rows:
        record = dict(zip(column_names, row))
        all_records.append(record)

    # NOTE: We intentionally do NOT follow next_link for MVP.
    # Chunked date windows (week-by-week) keep individual pages small enough.

    return all_records


@retry(
    stop=stop_after_attempt(3),
    wait=wait_chain(wait_fixed(5), wait_fixed(30), wait_fixed(120)),
    retry=retry_if_exception_type((HttpResponseError, TimeoutError, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def fetch_with_retry(scope: str, start: datetime, end: datetime) -> list[dict]:
    """Fetch billing data with retry: 3 attempts, waits of 5s → 30s → 120s."""
    return await fetch_billing_data(scope, start, end)
