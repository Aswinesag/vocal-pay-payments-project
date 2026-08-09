"""Database migration script to add hashed_password column to users table."""

import asyncio
from sqlalchemy import text
from app.database.database import async_engine


async def migrate():
    """Add hashed_password column if it doesn't exist."""
    print("=" * 60)
    print("VocalPay Database Migration")
    print("=" * 60)
    
    async with async_engine.begin() as conn:
        try:
            # Try to select the column
            result = await conn.execute(
                text("SELECT hashed_password FROM users LIMIT 1")
            )
            print("\n✅ hashed_password column already exists - no migration needed")
            
        except Exception as e:
            print(f"\n⚠️  Column doesn't exist, adding it now...")
            
            try:
                # Add the column
                await conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255) DEFAULT '' NOT NULL"
                    )
                )
                print("✅ Successfully added hashed_password column to users table")
                print("\n⚠️  IMPORTANT: Existing users will need to reset their passwords")
                print("   The default empty string '' is a placeholder.")
                
            except Exception as alter_error:
                print(f"\n❌ Failed to add column: {str(alter_error)}")
                print("\nManual SQL needed:")
                print("  ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255) DEFAULT '' NOT NULL;")
                raise
    
    print("\n" + "=" * 60)
    print("Migration Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(migrate())
