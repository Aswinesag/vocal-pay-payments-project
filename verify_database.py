"""Report record counts from the configured VocalPay database."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.database.database import async_engine


TABLES: tuple[str, ...] = (
    "users",
    "pending_transactions",
    "transactions",
    "fraud_events",
    "audit_logs",
)


async def verify_database() -> None:
    """Print record counts for every application table."""
    print(f"VocalPay database: {async_engine.url}")
    print("=" * 60)
    total = 0
    async with async_engine.connect() as conn:
        for table_name in TABLES:
            count = int(
                await conn.scalar(text(f'SELECT COUNT(*) FROM "{table_name}"'))
                or 0
            )
            total += count
            print(f"{table_name:25} {count} record(s)")

    print("=" * 60)
    if total == 0:
        print("Database is clean and ready for fresh signups.")
    else:
        print(f"Database contains {total} total record(s).")


async def main() -> None:
    """Run verification and dispose the engine."""
    try:
        await verify_database()
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
