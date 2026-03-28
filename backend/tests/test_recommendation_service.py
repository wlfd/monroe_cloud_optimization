"""
Unit tests for app.services.recommendation.

Covers:
- _make_cache_key: returns expected format
- _check_and_increment_counter: under limit, at limit, sets expiry on first call
- _get_calls_used_today: returns int from redis, returns 0 when None
- _build_prompt: returns string with resource info
- get_latest_recommendations: empty when no date, filtered results
- get_recommendation_summary: computes correct summary
- _get_or_generate: cache hit, cache miss calls LLM, limit reached returns None
"""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_scalar_result, make_scalars_result


# ---------------------------------------------------------------------------
# Shared resource fixture
# ---------------------------------------------------------------------------

SAMPLE_RESOURCE = {
    "resource_name": "vm-prod-01",
    "resource_group": "prod-rg",
    "subscription_id": "sub-001",
    "service_name": "Virtual Machines",
    "meter_category": "Compute",
    "monthly_cost": 2000.0,
    "cost_history": [
        {"date": "2026-03-01", "cost": 65.0},
        {"date": "2026-03-02", "cost": 70.0},
    ],
}


# ---------------------------------------------------------------------------
# _make_cache_key
# ---------------------------------------------------------------------------


def test_make_cache_key_format():
    """_make_cache_key returns rec:cache:{sub}:{rg}:{name}:{date}."""
    from app.services.recommendation import _make_cache_key

    fake_today = date(2026, 3, 15)

    with patch("app.services.recommendation.date") as mock_date:
        mock_date.today.return_value = fake_today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        key = _make_cache_key("sub-001", "prod-rg", "vm-01")

    assert key == "rec:cache:sub-001:prod-rg:vm-01:2026-03-15"


# ---------------------------------------------------------------------------
# _check_and_increment_counter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_and_increment_counter_under_limit():
    """Returns True when the counter is under the limit."""
    from app.services.recommendation import _check_and_increment_counter

    redis = AsyncMock()
    redis.incr.return_value = 5

    result = await _check_and_increment_counter(redis, limit=100)

    assert result is True
    redis.incr.assert_called_once()


@pytest.mark.asyncio
async def test_check_and_increment_counter_at_limit():
    """Returns False when the counter exceeds the limit."""
    from app.services.recommendation import _check_and_increment_counter

    redis = AsyncMock()
    redis.incr.return_value = 101

    result = await _check_and_increment_counter(redis, limit=100)

    assert result is False


@pytest.mark.asyncio
async def test_check_and_increment_counter_sets_expiry_on_first_call():
    """On the first call of the day (counter==1), EXPIREAT is set."""
    from app.services.recommendation import _check_and_increment_counter

    redis = AsyncMock()
    redis.incr.return_value = 1

    await _check_and_increment_counter(redis, limit=100)

    redis.expireat.assert_called_once()


@pytest.mark.asyncio
async def test_check_and_increment_counter_no_expiry_on_subsequent():
    """On subsequent calls (counter>1), EXPIREAT is NOT called."""
    from app.services.recommendation import _check_and_increment_counter

    redis = AsyncMock()
    redis.incr.return_value = 5

    await _check_and_increment_counter(redis, limit=100)

    redis.expireat.assert_not_called()


# ---------------------------------------------------------------------------
# _get_calls_used_today
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_calls_used_today_returns_int():
    """Returns the integer value from Redis."""
    from app.services.recommendation import _get_calls_used_today

    redis = AsyncMock()
    redis.get.return_value = b"42"

    result = await _get_calls_used_today(redis)

    assert result == 42


@pytest.mark.asyncio
async def test_get_calls_used_today_returns_zero_when_none():
    """Returns 0 when Redis key does not exist (returns None)."""
    from app.services.recommendation import _get_calls_used_today

    redis = AsyncMock()
    redis.get.return_value = None

    result = await _get_calls_used_today(redis)

    assert result == 0


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_contains_resource_info():
    """_build_prompt returns a string containing all resource fields."""
    from app.services.recommendation import _build_prompt

    prompt = _build_prompt(SAMPLE_RESOURCE)

    assert "vm-prod-01" in prompt
    assert "prod-rg" in prompt
    assert "sub-001" in prompt
    assert "Virtual Machines" in prompt
    assert "Compute" in prompt
    assert "$65.00" in prompt
    assert "$70.00" in prompt
    assert "cost optimization" in prompt.lower()


# ---------------------------------------------------------------------------
# get_latest_recommendations — no date (empty DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_latest_recommendations_empty_when_no_date():
    """Returns empty list when MAX(generated_date) is None."""
    from app.services.recommendation import get_latest_recommendations

    session = AsyncMock()

    # First call: max date query returns None
    session.execute.return_value = make_scalar_result(None)

    result = await get_latest_recommendations(session)

    assert result == []


# ---------------------------------------------------------------------------
# get_latest_recommendations — returns filtered results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_latest_recommendations_returns_results():
    """Returns recommendations filtered by the latest generated_date."""
    from app.services.recommendation import get_latest_recommendations

    session = AsyncMock()

    rec1 = MagicMock()
    rec1.category = "right-sizing"
    rec1.estimated_monthly_savings = Decimal("500")
    rec1.confidence_score = 85

    rec2 = MagicMock()
    rec2.category = "idle"
    rec2.estimated_monthly_savings = Decimal("200")
    rec2.confidence_score = 70

    # First call: max date
    max_date_result = make_scalar_result(date(2026, 3, 15))
    # Second call: filtered recommendations
    recs_result = make_scalars_result([rec1, rec2])

    session.execute.side_effect = [max_date_result, recs_result]

    result = await get_latest_recommendations(session)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_latest_recommendations_with_category_filter():
    """Passes category filter through to the query."""
    from app.services.recommendation import get_latest_recommendations

    session = AsyncMock()

    rec1 = MagicMock()
    rec1.category = "idle"

    max_date_result = make_scalar_result(date(2026, 3, 15))
    recs_result = make_scalars_result([rec1])

    session.execute.side_effect = [max_date_result, recs_result]

    result = await get_latest_recommendations(session, category="idle")

    assert len(result) == 1


# ---------------------------------------------------------------------------
# get_recommendation_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_recommendation_summary_computes_correctly():
    """get_recommendation_summary returns correct totals and category counts."""
    from app.services.recommendation import get_recommendation_summary

    session = AsyncMock()
    redis = AsyncMock()
    redis.get.return_value = b"25"

    rec1 = MagicMock()
    rec1.estimated_monthly_savings = Decimal("500")
    rec1.category = "right-sizing"

    rec2 = MagicMock()
    rec2.estimated_monthly_savings = Decimal("300")
    rec2.category = "idle"

    rec3 = MagicMock()
    rec3.estimated_monthly_savings = Decimal("200")
    rec3.category = "right-sizing"

    # get_latest_recommendations calls: max_date then scalars
    max_date_result = make_scalar_result(date(2026, 3, 15))
    recs_result = make_scalars_result([rec1, rec2, rec3])

    session.execute.side_effect = [max_date_result, recs_result]

    with patch("app.services.recommendation.get_settings") as mock_settings:
        mock_settings.return_value.LLM_DAILY_CALL_LIMIT = 100
        summary = await get_recommendation_summary(session, redis)

    assert summary["total_count"] == 3
    assert summary["potential_monthly_savings"] == 1000.0
    assert summary["by_category"]["right-sizing"] == 2
    assert summary["by_category"]["idle"] == 1
    assert summary["by_category"]["reserved"] == 0
    assert summary["by_category"]["storage"] == 0
    assert summary["calls_used_today"] == 25
    assert summary["daily_limit_reached"] is False


@pytest.mark.asyncio
async def test_get_recommendation_summary_limit_reached():
    """Summary shows daily_limit_reached=True when calls >= limit."""
    from app.services.recommendation import get_recommendation_summary

    session = AsyncMock()
    redis = AsyncMock()
    redis.get.return_value = b"100"

    # No recommendations
    max_date_result = make_scalar_result(None)
    session.execute.return_value = max_date_result

    with patch("app.services.recommendation.get_settings") as mock_settings:
        mock_settings.return_value.LLM_DAILY_CALL_LIMIT = 100
        summary = await get_recommendation_summary(session, redis)

    assert summary["total_count"] == 0
    assert summary["daily_limit_reached"] is True
    assert summary["calls_used_today"] == 100


# ---------------------------------------------------------------------------
# _get_or_generate — cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_generate_cache_hit():
    """On cache hit, returns cached result without calling LLM or incrementing counter."""
    from app.services.recommendation import _get_or_generate

    redis = AsyncMock()
    cached_result = {"category": "idle", "explanation": "VM is idle", "estimated_monthly_savings": 300, "confidence_score": 80}
    redis.get.return_value = json.dumps(cached_result).encode()

    anthropic_client = AsyncMock()

    result = await _get_or_generate(redis, anthropic_client, SAMPLE_RESOURCE, daily_limit=100)

    assert result == cached_result
    # LLM should NOT have been called
    anthropic_client.messages.create.assert_not_called()
    # Counter should NOT have been incremented
    redis.incr.assert_not_called()


# ---------------------------------------------------------------------------
# _get_or_generate — cache miss, calls LLM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_generate_cache_miss_calls_llm():
    """On cache miss with available limit, calls Anthropic and caches the result."""
    from app.services.recommendation import _get_or_generate

    redis = AsyncMock()
    redis.get.return_value = None  # cache miss
    redis.incr.return_value = 1   # first call, under limit

    llm_result = {
        "category": "right-sizing",
        "explanation": "Overprovisioned VM.",
        "estimated_monthly_savings": 500,
        "confidence_score": 85,
    }

    # Mock _call_anthropic
    anthropic_client = AsyncMock()

    with patch("app.services.recommendation._call_anthropic", new_callable=AsyncMock, return_value=llm_result):
        result = await _get_or_generate(redis, anthropic_client, SAMPLE_RESOURCE, daily_limit=100)

    assert result == llm_result
    # Should have cached the result
    redis.set.assert_called_once()
    cached_call = redis.set.call_args
    assert json.loads(cached_call.args[1]) == llm_result


# ---------------------------------------------------------------------------
# _get_or_generate — limit reached returns None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_or_generate_limit_reached_returns_none():
    """When daily limit is exceeded, returns None without calling LLM."""
    from app.services.recommendation import _get_or_generate

    redis = AsyncMock()
    redis.get.return_value = None   # cache miss
    redis.incr.return_value = 101   # over limit

    anthropic_client = AsyncMock()

    result = await _get_or_generate(redis, anthropic_client, SAMPLE_RESOURCE, daily_limit=100)

    assert result is None
    # LLM should NOT have been called
    anthropic_client.messages.create.assert_not_called()
