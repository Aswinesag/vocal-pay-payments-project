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