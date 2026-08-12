"""Authoritative FastAPI application assembly for VocalPay."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.transaction import router as transaction_router
from app.api.v1.endpoints.user import router as user_router
from app.core.config import settings
from app.core.constants import PROJECT_VERSION
from app.core.memory_manager import optimize_hardware_memory
from app.core.vector_index import initialize_voiceprint_index
from app.database.database import close_database, get_async_db, initialize_database


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize and release process-wide application resources."""
    logger.bind(application=settings.APP_NAME).info(
        "VocalPay application startup initiated."
    )
    try:
        await initialize_database()
        logger.bind(application=settings.APP_NAME).info(
            "Database initialized successfully."
        )
        
        # Initialize FAISS voiceprint index for rapid O(log n) voice identity resolution
        async for db in get_async_db():
            try:
                index_stats = await initialize_voiceprint_index(db)
                logger.bind(
                    **index_stats,
                    application=settings.APP_NAME
                ).info("FAISS voiceprint index initialized successfully.")
            finally:
                await db.close()
            break
        
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


@app.middleware("http")
async def schedule_memory_optimization(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Schedule hardware memory optimization after response delivery."""
    response = await call_next(request)
    background_tasks = BackgroundTasks()
    if response.background is not None:
        background_tasks.tasks.append(response.background)
    background_tasks.add_task(optimize_hardware_memory)
    response.background = background_tasks
    return response

app.include_router(auth_router, prefix="/api/v1")
app.include_router(transaction_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")

# Template configuration
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the VocalPay welcome page."""
    return templates.TemplateResponse("welcome.html", {"request": request})


@app.get("/signin", response_class=HTMLResponse)
async def signin_page(request: Request):
    """Serve the sign-in page."""
    return templates.TemplateResponse("signin.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Serve the sign-up page."""
    return templates.TemplateResponse("signup.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the user dashboard (old index.html)."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", response_model=dict[str, str])
async def health_check() -> dict[str, str]:
    """Return a lightweight application health response."""
    return {
        "application": settings.APP_NAME,
        "status": "operational",
        "version": PROJECT_VERSION,
    }
