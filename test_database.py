from app.database.database import (
    engine,
    SessionLocal,
    Base,
)

print()

print("========== DATABASE ==========")

print(engine)

print()

print("========== SESSION ==========")

db = SessionLocal()

print(type(db).__name__)

db.close()

print()

print("========== BASE ==========")

print(Base)

print()

print("database.py Section 1 validated.")

from app.database.database import (
    get_db,
    session_scope,
    check_database_connection,
)

print()

print("========== DATABASE DEPENDENCY ==========")

generator = get_db()

db = next(generator)

print(type(db).__name__)

db.close()

print()

print("========== SESSION SCOPE ==========")

with session_scope() as session:

    print(type(session).__name__)

print()

print("========== DATABASE HEALTH ==========")

print(check_database_connection())

from sqlalchemy import text

print()
print("========== SQLITE PRAGMAS ==========")

with SessionLocal() as db:

    foreign_keys = db.execute(
        text("PRAGMA foreign_keys;")
    ).scalar()

    journal = db.execute(
        text("PRAGMA journal_mode;")
    ).scalar()

    synchronous = db.execute(
        text("PRAGMA synchronous;")
    ).scalar()

    print("Foreign Keys :", foreign_keys)
    print("Journal Mode :", journal)
    print("Synchronous  :", synchronous)

from app.database.database import initialize_database

print()
print("========== DATABASE INITIALIZATION ==========")

initialize_database()

print("Initialization completed successfully.")

from app.database.database import validate_database

print()
print("========== DATABASE VALIDATION ==========")

print("Database Ready :", validate_database())

from app.database.database import (
    shutdown_database,
    get_database_information,
    get_engine,
)

print()
print("========== DATABASE INFORMATION ==========")

info = get_database_information()

for key, value in info.items():
    print(f"{key:<15}: {value}")

print()

print("========== ENGINE ==========")

print(get_engine())

print()

print("========== SHUTDOWN ==========")

shutdown_database()

print("Shutdown completed successfully.")