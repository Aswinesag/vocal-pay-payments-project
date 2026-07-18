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

from app.database.models import FraudEvent
from app.database.database import Base

print()
print("========== FRAUD EVENT MODEL ==========")

print(FraudEvent.__tablename__)

print()

print(list(Base.metadata.tables.keys()))

from app.database.models import AuditLog
from app.database.database import Base

print()
print("========== AUDIT LOG MODEL ==========")

print(AuditLog.__tablename__)

print()

print(list(Base.metadata.tables.keys()))

from app.database.database import Base

print()
print("========== ALL TABLES ==========")

for table in Base.metadata.sorted_tables:
    print(table.name)

print()

print("Total Tables:", len(Base.metadata.tables))

from app.database.models import User

print()
print("========== USER RELATIONSHIPS ==========")

print(User.pending_transactions.property)
print(User.transactions.property)
print(User.fraud_events.property)
print(User.audit_logs.property)

from app.database.models import User

print(hasattr(User, "pending_transactions"))
print(dir(User))