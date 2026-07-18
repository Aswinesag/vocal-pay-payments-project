from app.database.models import (
    TimestampMixin,
    PrimaryKeyMixin,
    TransactionIDMixin,
)

print()

print("========== MIXINS ==========")

print(TimestampMixin)
print(PrimaryKeyMixin)
print(TransactionIDMixin)

print()

print("models.py Section 1 validated.")

from app.database.models import User

print()
print("========== USER MODEL ==========")

print(User.__tablename__)

print(User)

from app.database.database import Base

print()
print("========== REGISTERED TABLES ==========")

print(list(Base.metadata.tables.keys()))

from app.database.models import PendingTransaction
from app.database.database import Base

print()
print("========== PENDING TRANSACTION ==========")

print(PendingTransaction.__tablename__)

print()

print(Base.metadata.tables.keys())

from app.database.models import Transaction
from app.database.database import Base

print()
print("========== TRANSACTION MODEL ==========")

print(Transaction.__tablename__)

print()

print(list(Base.metadata.tables.keys()))