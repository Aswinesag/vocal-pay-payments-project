"""Delete all VocalPay records while preserving the configured schema."""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.database.database import async_engine


TABLES_IN_DELETE_ORDER: tuple[str, ...] = (
    "audit_logs",
    "fraud_events",
    "transactions",
    "pending_transactions",
    "users",
)


async def clear_database() -> None:
    """Delete every record from the configured VocalPay database."""
    print(f"Clearing configured database: {async_engine.url}")
    async with async_engine.begin() as conn:
        for table_name in TABLES_IN_DELETE_ORDER:
            result = await conn.execute(text(f'DELETE FROM "{table_name}"'))
            print(f"Deleted {result.rowcount} record(s) from {table_name}.")

        sequence_exists = await conn.scalar(
            text(
                "SELECT 1 FROM sqlite_master "
                "WHERE type = 'table' AND name = 'sqlite_sequence'"
            )
        )
        if sequence_exists is not None:
            await conn.execute(text("DELETE FROM sqlite_sequence"))
            print("Reset SQLite autoincrement counters.")

    print("Database records cleared successfully.")


async def main() -> None:
    """Run the cleanup and dispose the engine."""
    try:
        await clear_database()
    finally:
        await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
