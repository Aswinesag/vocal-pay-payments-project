import asyncio

from app.database.crud import (
    DBSession,
    get_db_session,
    utc_now,
)

print("\n========== CRUD FOUNDATION ==========")

print(DBSession)

print("\n========== UTC NOW ==========")

print(utc_now())


async def test_session():
    async with get_db_session() as db:
        print("\n========== SESSION ==========")
        print(type(db).__name__)


asyncio.run(test_session())

from app.database.crud import create_user
from app.database.database import AsyncSessionLocal
from app.database.schemas import UserRegistrationRequest


async def test_create_user():
    async with AsyncSessionLocal() as session:

        user = await create_user(
            session,
            UserRegistrationRequest(
                user_id="USR0001",
                full_name="Test User",
                email="test@example.com",
                phone_number="9876543210",
                preferred_language="en",
                speaker_embedding=[0.1] * 192,
                face_embedding=[0.2] * 512,
            ),
        )

        print("\n========== CREATE USER ==========")
        print(user.user_id)
        print(user.email)

        await session.rollback()


asyncio.run(test_create_user())

from app.database.crud import (
    activate_user,
    create_pending_transaction,
    create_transaction,
    create_fraud_event,
    create_audit_log,
    create_user,
    deactivate_user,
    delete_expired_pending_transactions,
    delete_pending_transaction,
    extend_pending_expiry,
    get_fraud_event_by_transaction_id,
    get_fraud_detection_rate,
    get_fraud_event_count,
    get_fraud_events_by_user_id,
    get_audit_logs_by_transaction_id,
    get_audit_logs_by_user_id,
    get_audit_log_count,
    get_logs_by_action,
    get_logs_by_actor,
    get_logs_by_time_range,
    get_blocked_events,
    get_high_risk_events,
    get_recent_fraud_events,
    get_recent_audit_logs,
    get_replay_attack_events,
    get_pending_transaction_by_transaction_id,
    get_pending_transaction_by_verification_secret,
    get_average_transaction_amount,
    get_failed_transaction_count,
    get_recent_transactions,
    get_successful_transaction_count,
    get_total_transaction_amount,
    get_transaction_count,
    get_transaction_by_transaction_id,
    get_transactions_by_user_id,
    get_user_by_email,
    get_user_by_phone,
    get_user_by_user_id,
    increment_failed_attempts,
    reset_failed_attempts,
    update_biometric_embeddings,
    update_last_login,
    update_pending_status,
    update_user_profile,
)


async def test_user_queries():
    async with AsyncSessionLocal() as session:

        user = await create_user(
            session,
            UserRegistrationRequest(
                user_id="USR0002",
                full_name="Lookup Test",
                email="lookup@example.com",
                phone_number="9123456789",
                preferred_language="en",
                speaker_embedding=[0.1] * 192,
                face_embedding=[0.2] * 512,
            ),
        )

        # Make the row visible within the transaction
        await session.flush()

        print("\n========== USER LOOKUPS ==========")

        by_id = await get_user_by_user_id(session, "USR0002")
        print("User ID:", by_id.user_id if by_id else None)

        by_email = await get_user_by_email(session, "lookup@example.com")
        print("Email:", by_email.email if by_email else None)

        by_phone = await get_user_by_phone(session, "9123456789")
        print("Phone:", by_phone.phone_number if by_phone else None)

        missing = await get_user_by_user_id(session, "UNKNOWN")
        print("Missing:", missing)

        await session.rollback()


asyncio.run(test_user_queries())

async def test_user_updates():
    async with AsyncSessionLocal() as session:

        user = await create_user(
            session,
            UserRegistrationRequest(
                user_id="USR0003",
                full_name="Original Name",
                email="original@example.com",
                phone_number="9000000000",
                preferred_language="en",
                speaker_embedding=[0.1] * 192,
                face_embedding=[0.2] * 512,
            ),
        )

        await update_user_profile(
            session,
            user,
            full_name="Updated Name",
            preferred_language="hi",
        )

        await update_biometric_embeddings(
            session,
            user,
            speaker_embedding=[0.5] * 192,
        )

        print("\n========== USER UPDATE ==========")
        print(user.full_name)
        print(user.preferred_language)
        print(len(user.speaker_embedding))

        await session.rollback()


asyncio.run(test_user_updates())

async def test_user_account_state():
    async with AsyncSessionLocal() as session:

        user = await create_user(
            session,
            UserRegistrationRequest(
                user_id="USR0004",
                full_name="Security Test",
                email="security@example.com",
                phone_number="9111111111",
                preferred_language="en",
                speaker_embedding=[0.1] * 192,
                face_embedding=[0.2] * 512,
            ),
        )

        print("\n========== ACCOUNT STATE ==========")

        await increment_failed_attempts(session, user)
        await increment_failed_attempts(session, user)
        print("Failed Attempts:", user.failed_attempts)

        await reset_failed_attempts(session, user)
        print("Reset:", user.failed_attempts)

        await deactivate_user(session, user)
        print("Active:", user.is_active)

        await activate_user(session, user)
        print("Reactivated:", user.is_active)

        await update_last_login(session, user)
        print("Last Login:", user.last_login_at)

        await session.rollback()


asyncio.run(test_user_account_state())

from datetime import timedelta

from app.database.models import AuditLog, FraudEvent, PendingTransaction, Transaction


async def test_create_pending_transaction():
    async with AsyncSessionLocal() as session:

        pending = PendingTransaction(
            transaction_id="TXN000001",
            user_id="USR0004",
            amount=2500.00,
            risk_level="HIGH",
            status="PENDING_CHALLENGE",
            verification_secret="challenge-123",
            expires_at=utc_now() + timedelta(minutes=5),
            speaker_score=0.97,
            face_score=0.98,
            fraud_score=0.18,
            replay_attack=False,
        )

        await create_pending_transaction(
            session,
            pending,
        )

        print("\n========== PENDING TRANSACTION ==========")
        print(pending.transaction_id)
        print(pending.status)

        await session.rollback()


asyncio.run(test_create_pending_transaction())

async def test_pending_transaction_lookup():
    async with AsyncSessionLocal() as session:

        pending = PendingTransaction(
            transaction_id="TXN000002",
            user_id="USR0004",
            amount=1500.00,
            risk_level="MEDIUM",
            status="PENDING_OTP",
            verification_secret="OTP123456",
            expires_at=utc_now() + timedelta(minutes=5),
            speaker_score=0.96,
            face_score=0.98,
            fraud_score=0.12,
            replay_attack=False,
        )

        await create_pending_transaction(session, pending)

        print("\n========== PENDING LOOKUP ==========")

        txn = await get_pending_transaction_by_transaction_id(
            session,
            "TXN000002",
        )
        print("Transaction:", txn.transaction_id if txn else None)

        secret = await get_pending_transaction_by_verification_secret(
            session,
            "OTP123456",
        )
        print(
            "Verification Secret:",
            secret.verification_secret if secret else None,
        )

        missing = await get_pending_transaction_by_transaction_id(
            session,
            "UNKNOWN",
        )
        print("Missing:", missing)

        await session.rollback()


asyncio.run(test_pending_transaction_lookup())

async def test_pending_updates():
    async with AsyncSessionLocal() as session:

        pending = PendingTransaction(
            transaction_id="TXN000003",
            user_id="USR0004",
            amount=5000.00,
            risk_level="HIGH",
            status="PENDING_CHALLENGE",
            verification_secret="challenge-xyz",
            expires_at=utc_now() + timedelta(minutes=5),
            speaker_score=0.98,
            face_score=0.99,
            fraud_score=0.15,
            replay_attack=False,
        )

        await create_pending_transaction(session, pending)

        await update_pending_status(
            session,
            pending,
            "VERIFIED",
        )

        await extend_pending_expiry(
            session,
            pending,
            timedelta(minutes=2),
        )

        print("\n========== PENDING UPDATE ==========")
        print("Status:", pending.status)
        print("Expires:", pending.expires_at)

        await session.rollback()


asyncio.run(test_pending_updates())

async def test_pending_cleanup():
    async with AsyncSessionLocal() as session:

        expired = PendingTransaction(
            transaction_id="TXN_EXPIRED",
            user_id="USR0004",
            amount=100.0,
            risk_level="LOW",
            status="EXPIRED",
            verification_secret="expired-secret",
            expires_at=utc_now() - timedelta(minutes=10),
            speaker_score=0.95,
            face_score=0.96,
            fraud_score=0.05,
            replay_attack=False,
        )

        active = PendingTransaction(
            transaction_id="TXN_ACTIVE",
            user_id="USR0004",
            amount=200.0,
            risk_level="MEDIUM",
            status="PENDING_OTP",
            verification_secret="active-secret",
            expires_at=utc_now() + timedelta(minutes=5),
            speaker_score=0.97,
            face_score=0.98,
            fraud_score=0.08,
            replay_attack=False,
        )

        await create_pending_transaction(session, expired)
        await create_pending_transaction(session, active)

        deleted = await delete_expired_pending_transactions(session)

        print("\n========== CLEANUP ==========")
        print("Deleted:", deleted)

        remaining = await get_pending_transaction_by_transaction_id(
            session,
            "TXN_ACTIVE",
        )

        print("Active Exists:", remaining is not None)

        await delete_pending_transaction(session, active)

        remaining = await get_pending_transaction_by_transaction_id(
            session,
            "TXN_ACTIVE",
        )

        print("Deleted Individually:", remaining is None)

        await session.rollback()


asyncio.run(test_pending_cleanup())

async def test_create_transaction():
    async with AsyncSessionLocal() as session:

        transaction = Transaction(
            transaction_id="TXN_FINAL_001",
            user_id="USR0004",
            amount=1500.00,
            status="SUCCESS",
            risk_level="LOW",
            success=True,
            speaker_score=0.98,
            face_score=0.99,
            fraud_score=0.04,
            replay_attack=False,
            xai_reason="Transaction approved.",
            processing_time_ms=125.0,
        )

        await create_transaction(session, transaction)

        print("\n========== CREATE TRANSACTION ==========")
        print(transaction.transaction_id)
        print(transaction.status)

        await session.rollback()


asyncio.run(test_create_transaction())

async def test_transaction_lookup():
    async with AsyncSessionLocal() as session:

        tx1 = Transaction(
            transaction_id="TXN1001",
            user_id="USR0004",
            amount=500.0,
            status="SUCCESS",
            risk_level="LOW",
            success=True,
            speaker_score=0.98,
            face_score=0.99,
            fraud_score=0.04,
            replay_attack=False,
            xai_reason="Approved.",
            processing_time_ms=100.0,
        )

        tx2 = Transaction(
            transaction_id="TXN1002",
            user_id="USR0004",
            amount=1000.0,
            status="SUCCESS",
            risk_level="LOW",
            success=True,
            speaker_score=0.97,
            face_score=0.98,
            fraud_score=0.06,
            replay_attack=False,
            xai_reason="Approved.",
            processing_time_ms=110.0,
        )

        await create_transaction(session, tx1)
        await create_transaction(session, tx2)

        print("\n========== TRANSACTION LOOKUP ==========")

        transaction = await get_transaction_by_transaction_id(
            session,
            "TXN1001",
        )

        print("Transaction:", transaction.transaction_id)

        transactions = await get_transactions_by_user_id(
            session,
            "USR0004",
        )

        print("Count:", len(transactions))

        for tx in transactions:
            print(tx.transaction_id)

        await session.rollback()


asyncio.run(test_transaction_lookup())

async def test_transaction_statistics():
    async with AsyncSessionLocal() as session:

        tx1 = Transaction(
            transaction_id="TXN2001",
            user_id="USR0004",
            amount=100.0,
            status="SUCCESS",
            risk_level="LOW",
            success=True,
            speaker_score=0.98,
            face_score=0.99,
            fraud_score=0.03,
            replay_attack=False,
            xai_reason="Approved.",
            processing_time_ms=90.0,
        )

        tx2 = Transaction(
            transaction_id="TXN2002",
            user_id="USR0004",
            amount=250.0,
            status="SUCCESS",
            risk_level="LOW",
            success=True,
            speaker_score=0.97,
            face_score=0.98,
            fraud_score=0.04,
            replay_attack=False,
            xai_reason="Approved.",
            processing_time_ms=95.0,
        )

        await create_transaction(session, tx1)
        await create_transaction(session, tx2)

        print("\n========== TRANSACTION STATS ==========")

        recent = await get_recent_transactions(
            session,
            limit=5,
        )

        print("Recent:", len(recent))

        total = await get_transaction_count(session)
        print("Total:", total)

        user_total = await get_transaction_count(
            session,
            user_id="USR0004",
        )

        print("User Total:", user_total)

        await session.rollback()


asyncio.run(test_transaction_statistics())

async def test_transaction_analytics():
    async with AsyncSessionLocal() as session:

        tx1 = Transaction(
            transaction_id="TXN3001",
            user_id="USR0004",
            amount=100.0,
            status="SUCCESS",
            risk_level="LOW",
            success=True,
            speaker_score=0.98,
            face_score=0.99,
            fraud_score=0.02,
            replay_attack=False,
            xai_reason="Approved.",
            processing_time_ms=90.0,
        )

        tx2 = Transaction(
            transaction_id="TXN3002",
            user_id="USR0004",
            amount=300.0,
            status="FAILED",
            risk_level="HIGH",
            success=False,
            speaker_score=0.60,
            face_score=0.70,
            fraud_score=0.91,
            replay_attack=False,
            xai_reason="Rejected.",
            processing_time_ms=110.0,
        )

        await create_transaction(session, tx1)
        await create_transaction(session, tx2)

        print("\n========== TRANSACTION ANALYTICS ==========")

        print(
            "Total Amount:",
            await get_total_transaction_amount(session),
        )

        print(
            "Successful:",
            await get_successful_transaction_count(session),
        )

        print(
            "Failed:",
            await get_failed_transaction_count(session),
        )

        print(
            "Average:",
            await get_average_transaction_amount(session),
        )

        await session.rollback()


asyncio.run(test_transaction_analytics())

async def test_create_fraud_event():
    async with AsyncSessionLocal() as session:

        fraud = FraudEvent(
            transaction_id="TXN4001",
            user_id="USR0004",
            event_type="VOICE_ANOMALY",
            risk_level="HIGH",
            blocked=True,
            replay_attack=False,
            speaker_score=0.71,
            face_score=0.82,
            fraud_score=0.91,
            reason="Voice anomaly detected.",
        )

        await create_fraud_event(
            session,
            fraud,
        )

        print("\n========== FRAUD EVENT ==========")
        print(fraud.transaction_id)
        print(fraud.risk_level)
        print(fraud.blocked)

        await session.rollback()


asyncio.run(test_create_fraud_event())

async def test_fraud_event_lookup():
    async with AsyncSessionLocal() as session:

        fraud1 = FraudEvent(
            transaction_id="TXN5001",
            user_id="USR0004",
            event_type="VOICE_MISMATCH",
            risk_level="HIGH",
            blocked=True,
            replay_attack=False,
            speaker_score=0.74,
            face_score=0.81,
            fraud_score=0.91,
            reason="Voice mismatch detected.",
        )

        fraud2 = FraudEvent(
            transaction_id="TXN5002",
            user_id="USR0004",
            event_type="ADDITIONAL_VERIFICATION",
            risk_level="MEDIUM",
            blocked=False,
            replay_attack=False,
            speaker_score=0.92,
            face_score=0.95,
            fraud_score=0.63,
            reason="Additional verification required.",
        )

        await create_fraud_event(session, fraud1)
        await create_fraud_event(session, fraud2)

        print("\n========== FRAUD LOOKUP ==========")

        event = await get_fraud_event_by_transaction_id(
            session,
            "TXN5001",
        )

        print("Transaction:", event.transaction_id if event else None)

        events = await get_fraud_events_by_user_id(
            session,
            "USR0004",
        )

        print("Count:", len(events))

        for item in events:
            print(item.transaction_id)

        missing = await get_fraud_event_by_transaction_id(
            session,
            "UNKNOWN",
        )

        print("Missing:", missing)

        await session.rollback()


asyncio.run(test_fraud_event_lookup())

async def test_fraud_analytics():
    async with AsyncSessionLocal() as session:

        event1 = FraudEvent(
            transaction_id="TXN6001",
            user_id="USR0004",
            fraud_score=0.95,
            event_type="HIGH_FRAUD_CONFIDENCE",
            risk_level="HIGH",
            blocked=True,
            replay_attack=False,
            speaker_score=0.71,
            face_score=0.80,
            reason="High fraud confidence.",
        )

        event2 = FraudEvent(
            transaction_id="TXN6002",
            user_id="USR0004",
            fraud_score=0.35,
            event_type="LOW_RISK",
            risk_level="LOW",
            blocked=False,
            replay_attack=False,
            speaker_score=0.97,
            face_score=0.98,
            reason="Low risk.",
        )

        await create_fraud_event(session, event1)
        await create_fraud_event(session, event2)

        print("\n========== FRAUD ANALYTICS ==========")

        high = await get_high_risk_events(
            session,
            threshold=0.90,
        )

        print("High Risk:", len(high))

        count = await get_fraud_event_count(session)
        print("Count:", count)

        rate = await get_fraud_detection_rate(session)
        print(f"Detection Rate: {rate:.2f}%")

        await session.rollback()


asyncio.run(test_fraud_analytics())

async def test_fraud_investigation_queries():
    async with AsyncSessionLocal() as session:

        event1 = FraudEvent(
            transaction_id="TXN7001",
            user_id="USR0004",
            fraud_score=0.96,
            event_type="REPLAY_ATTACK",
            risk_level="HIGH",
            blocked=True,
            replay_attack=True,
            speaker_score=0.62,
            face_score=0.73,
            reason="Replay attack detected.",
        )

        event2 = FraudEvent(
            transaction_id="TXN7002",
            user_id="USR0004",
            fraud_score=0.42,
            event_type="NO_ANOMALY",
            risk_level="LOW",
            blocked=False,
            replay_attack=False,
            speaker_score=0.98,
            face_score=0.99,
            reason="No anomaly detected.",
        )

        await create_fraud_event(session, event1)
        await create_fraud_event(session, event2)

        print("\n========== FRAUD INVESTIGATION ==========")

        replay = await get_replay_attack_events(session)
        print("Replay:", len(replay))

        blocked = await get_blocked_events(session)
        print("Blocked:", len(blocked))

        recent = await get_recent_fraud_events(session)
        print("Recent:", len(recent))

        if replay:
            print("Replay TX:", replay[0].transaction_id)

        await session.rollback()


asyncio.run(test_fraud_investigation_queries())

async def test_create_audit_log():
    async with AsyncSessionLocal() as session:

        audit = AuditLog(
            transaction_id="TXN8001",
            user_id="USR0004",
            endpoint="/transactions",
            method="SYSTEM",
            event_type="TRANSACTION_CREATED",
            status="SUCCESS",
            message="Transaction successfully created.",
        )

        await create_audit_log(
            session,
            audit,
        )

        print("\n========== AUDIT LOG ==========")
        print(audit.transaction_id)
        print(audit.event_type)
        print(audit.method)

        await session.rollback()


asyncio.run(test_create_audit_log())

async def test_audit_log_lookup():
    async with AsyncSessionLocal() as session:

        log1 = AuditLog(
            transaction_id="TXN8002",
            user_id="USR0004",
            endpoint="/verification/voice",
            method="SYSTEM",
            event_type="VOICE_VERIFIED",
            status="SUCCESS",
            message="Voice authentication passed.",
        )

        log2 = AuditLog(
            transaction_id="TXN8003",
            user_id="USR0004",
            endpoint="/verification/face",
            method="SYSTEM",
            event_type="FACE_VERIFIED",
            status="SUCCESS",
            message="Face authentication passed.",
        )

        await create_audit_log(session, log1)
        await create_audit_log(session, log2)

        print("\n========== AUDIT LOOKUP ==========")

        tx_logs = await get_audit_logs_by_transaction_id(
            session,
            "TXN8002",
        )

        print("Transaction Logs:", len(tx_logs))

        for log in tx_logs:
            print(log.event_type)

        user_logs = await get_audit_logs_by_user_id(
            session,
            "USR0004",
        )

        print("User Logs:", len(user_logs))

        await session.rollback()


asyncio.run(test_audit_log_lookup())

async def test_audit_monitoring():
    async with AsyncSessionLocal() as session:

        log1 = AuditLog(
            transaction_id="TXN9001",
            user_id="USR0004",
            endpoint="/login",
            method="SYSTEM",
            event_type="LOGIN",
            status="SUCCESS",
            message="User logged in.",
        )

        log2 = AuditLog(
            transaction_id="TXN9002",
            user_id="USR0004",
            endpoint="/transactions/approve",
            method="SYSTEM",
            event_type="TRANSACTION_APPROVED",
            status="SUCCESS",
            message="Transaction approved.",
        )

        await create_audit_log(session, log1)
        await create_audit_log(session, log2)

        print("\n========== AUDIT MONITORING ==========")

        recent = await get_recent_audit_logs(
            session,
            limit=10,
        )

        print("Recent:", len(recent))

        total = await get_audit_log_count(session)
        print("Total:", total)

        user_total = await get_audit_log_count(
            session,
            user_id="USR0004",
        )

        print("User Total:", user_total)

        if recent:
            print("Latest Action:", recent[0].event_type)

        await session.rollback()


asyncio.run(test_audit_monitoring())

async def test_audit_investigation_queries():
    async with AsyncSessionLocal() as session:

        now = utc_now()

        log1 = AuditLog(
            transaction_id="TXN9101",
            user_id="USR0004",
            endpoint="/verification/voice",
            method="SYSTEM",
            event_type="VOICE_VERIFIED",
            status="SUCCESS",
            message="Voice verification successful.",
        )

        log2 = AuditLog(
            transaction_id="TXN9102",
            user_id="USR0004",
            endpoint="/login",
            method="USER",
            event_type="LOGIN",
            status="SUCCESS",
            message="User login.",
        )

        await create_audit_log(session, log1)
        await create_audit_log(session, log2)

        print("\n========== AUDIT INVESTIGATION ==========")

        actions = await get_logs_by_action(
            session,
            "VOICE_VERIFIED",
        )
        print("Action:", len(actions))

        actors = await get_logs_by_actor(
            session,
            "SYSTEM",
        )
        print("Actor:", len(actors))

        timerange = await get_logs_by_time_range(
            session,
            now - timedelta(minutes=5),
            now + timedelta(minutes=5),
        )
        print("Time Range:", len(timerange))

        if timerange:
            print("First:", timerange[0].event_type)

        await session.rollback()


asyncio.run(test_audit_investigation_queries())
