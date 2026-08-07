"""Authoritative FastAPI application assembly for VocalPay."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1.endpoints.transaction import router as transaction_router
from app.core.config import settings
from app.core.constants import PROJECT_VERSION
from app.database.database import close_database, initialize_database


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize and release process-wide application resources."""
    logger.bind(application=settings.APP_NAME).info(
        "VocalPay application startup initiated."
    )
    try:
        await initialize_database()
        logger.bind(application=settings.APP_NAME).info(
            "VocalPay application startup completed."
        )
        yield
    except Exception:
        logger.bind(application=settings.APP_NAME).exception(
            "VocalPay application lifecycle failed."
        )
        raise
    finally:
        try:
            await close_database()
        except Exception:
            logger.bind(application=settings.APP_NAME).exception(
                "VocalPay database shutdown failed."
            )
        else:
            logger.bind(application=settings.APP_NAME).info(
                "VocalPay application shutdown completed."
            )


app = FastAPI(
    title=settings.APP_NAME,
    description="Secure multimodal biometric transaction backend.",
    version=PROJECT_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transaction_router, prefix="/api/v1")


@app.get("/", response_model=dict[str, str])
async def health_check() -> dict[str, str]:
    """Return a lightweight application health response."""
    return {
        "application": settings.APP_NAME,
        "status": "operational",
        "version": PROJECT_VERSION,
    }
