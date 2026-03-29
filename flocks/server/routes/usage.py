"""
Usage tracking API routes

Provides endpoints for recording and querying LLM usage and costs.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from flocks.provider.cost_calculator import CostCalculator
from flocks.provider.types import PriceConfig, UsageCost, UsageRecord
from flocks.storage.storage import Storage
from flocks.utils.log import Log

router = APIRouter()
log = Log.create(service="routes.usage")


# ==================== Request / Response Models ====================


class RecordUsageRequest(BaseModel):
    """Record a usage entry"""
    provider_id: str
    model_id: str
    credential_id: Optional[str] = None
    session_id: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    latency_ms: Optional[int] = None
    # Optional: pass pricing to auto-calculate cost
    pricing: Optional[PriceConfig] = None


class UsageSummary(BaseModel):
    """Aggregated usage summary"""
    total_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    total_requests: int = 0
    currency: str = "USD"


class ProviderUsageSummary(BaseModel):
    """Usage summary per provider"""
    provider_id: str
    total_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0


class ModelUsageSummary(BaseModel):
    """Usage summary per model"""
    provider_id: str
    model_id: str
    total_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0


class DailyUsageSummary(BaseModel):
    """Usage summary per day"""
    date: str
    total_tokens: int = 0
    total_cost: float = 0.0
    request_count: int = 0


class UsageStatsResponse(BaseModel):
    """Full usage statistics"""
    summary: UsageSummary
    by_provider: List[ProviderUsageSummary]
    by_model: List[ModelUsageSummary]
    daily: List[DailyUsageSummary]


# ==================== Service Functions ====================


async def record_usage(req: RecordUsageRequest) -> UsageRecord:
    """Record a usage entry to the database."""
    await Storage._ensure_init()

    record_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    total_tokens = req.input_tokens + req.output_tokens + req.reasoning_tokens

    # Calculate cost if pricing provided
    input_cost = 0.0
    output_cost = 0.0
    total_cost = 0.0
    currency = "USD"

    if req.pricing:
        cost = CostCalculator.calculate(
            input_tokens=req.input_tokens,
            output_tokens=req.output_tokens,
            pricing=req.pricing,
            cached_tokens=req.cached_tokens,
        )
        input_cost = cost.input_cost
        output_cost = cost.output_cost
        total_cost = cost.total_cost
        currency = cost.currency

    async with aiosqlite.connect(Storage._db_path) as db:
        await db.execute(
            """INSERT INTO usage_records
               (id, provider_id, model_id, credential_id, session_id,
                input_tokens, output_tokens, cached_tokens, reasoning_tokens,
                total_tokens, input_cost, output_cost, total_cost, currency,
                latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record_id, req.provider_id, req.model_id,
                req.credential_id, req.session_id,
                req.input_tokens, req.output_tokens, req.cached_tokens,
                req.reasoning_tokens, total_tokens,
                input_cost, output_cost, total_cost, currency,
                req.latency_ms, now,
            ),
        )
        await db.commit()

    return UsageRecord(
        id=record_id,
        provider_id=req.provider_id,
        model_id=req.model_id,
        credential_id=req.credential_id,
        session_id=req.session_id,
        input_tokens=req.input_tokens,
        output_tokens=req.output_tokens,
        cached_tokens=req.cached_tokens,
        reasoning_tokens=req.reasoning_tokens,
        total_tokens=total_tokens,
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=total_cost,
        currency=currency,
        latency_ms=req.latency_ms,
        created_at=datetime.fromisoformat(now),
    )


# ==================== Routes ====================


@router.post(
    "/record",
    response_model=UsageRecord,
    summary="Record usage",
    description="Record a single LLM usage entry",
)
async def api_record_usage(body: RecordUsageRequest) -> UsageRecord:
    """Record an LLM usage entry."""
    return await record_usage(body)


async def _query_usage_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    provider_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> UsageStatsResponse:
    """Internal usage stats query (decoupled from FastAPI Query objects)."""
    await Storage._ensure_init()

    where_clauses = []
    params = []

    if start_date:
        where_clauses.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("created_at <= ?")
        params.append(end_date)
    if provider_id:
        where_clauses.append("provider_id = ?")
        params.append(provider_id)
    if model_id:
        where_clauses.append("model_id = ?")
        params.append(model_id)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    async with aiosqlite.connect(Storage._db_path) as db:
        db.row_factory = aiosqlite.Row

        # Overall summary
        async with db.execute(
            f"""SELECT
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(total_cost), 0) as total_cost,
                COUNT(*) as total_requests
            FROM usage_records{where_sql}""",
            params,
        ) as cursor:
            row = await cursor.fetchone()

        summary = UsageSummary(
            total_tokens=row["total_tokens"],
            total_input_tokens=row["total_input"],
            total_output_tokens=row["total_output"],
            total_cost=round(row["total_cost"], 6),
            total_requests=row["total_requests"],
        )

        # By provider
        async with db.execute(
            f"""SELECT provider_id,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(total_cost), 0) as total_cost,
                COUNT(*) as cnt
            FROM usage_records{where_sql}
            GROUP BY provider_id
            ORDER BY total_cost DESC""",
            params,
        ) as cursor:
            rows = await cursor.fetchall()

        by_provider = [
            ProviderUsageSummary(
                provider_id=r["provider_id"],
                total_tokens=r["total_tokens"],
                total_cost=round(r["total_cost"], 6),
                request_count=r["cnt"],
            )
            for r in rows
        ]

        # By model
        async with db.execute(
            f"""SELECT provider_id, model_id,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(total_cost), 0) as total_cost,
                COUNT(*) as cnt
            FROM usage_records{where_sql}
            GROUP BY provider_id, model_id
            ORDER BY total_cost DESC""",
            params,
        ) as cursor:
            rows = await cursor.fetchall()

        by_model = [
            ModelUsageSummary(
                provider_id=r["provider_id"],
                model_id=r["model_id"],
                total_tokens=r["total_tokens"],
                total_cost=round(r["total_cost"], 6),
                request_count=r["cnt"],
            )
            for r in rows
        ]

        # Daily
        async with db.execute(
            f"""SELECT DATE(created_at) as date,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(total_cost), 0) as total_cost,
                COUNT(*) as cnt
            FROM usage_records{where_sql}
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 90""",
            params,
        ) as cursor:
            rows = await cursor.fetchall()

        daily = [
            DailyUsageSummary(
                date=r["date"],
                total_tokens=r["total_tokens"],
                total_cost=round(r["total_cost"], 6),
                request_count=r["cnt"],
            )
            for r in rows
        ]

    return UsageStatsResponse(
        summary=summary,
        by_provider=by_provider,
        by_model=by_model,
        daily=daily,
    )


# Public alias for direct (non-FastAPI) callers
get_usage_stats = _query_usage_stats


@router.get(
    "/summary",
    response_model=UsageStatsResponse,
    summary="Get usage statistics",
    description="Get aggregated usage statistics with optional date range",
)
async def api_get_usage_stats(
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    provider_id: Optional[str] = Query(None, description="Filter by provider"),
    model_id: Optional[str] = Query(None, description="Filter by model"),
) -> UsageStatsResponse:
    """Get aggregated usage statistics (HTTP route handler)."""
    return await _query_usage_stats(
        start_date=start_date, end_date=end_date,
        provider_id=provider_id, model_id=model_id,
    )
