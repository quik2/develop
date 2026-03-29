# main.py — Develop backend. FastAPI server that proxies photo enhancement through OpenAI.

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from openai import AsyncOpenAI

from database import (
    cleanup_old_jobs,
    complete_job,
    create_job,
    ensure_user,
    fail_job,
    get_db,
    get_job,
    get_usage,
    increment_usage,
    init_db,
    update_user_tier,
)
from enhancement import enhance_image

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("develop")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REVENUECAT_WEBHOOK_SECRET = os.getenv("REVENUECAT_WEBHOOK_SECRET", "")

FREE_DAILY_LIMIT = 5
PRO_MONTHLY_LIMIT = 200

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup, cleanup on shutdown."""
    await init_db()
    logger.info("Database initialized")

    # Periodic cleanup task
    async def periodic_cleanup():
        while True:
            await asyncio.sleep(3600)  # every hour
            try:
                db = await get_db()
                await cleanup_old_jobs(db)
                await db.close()
                logger.info("Old jobs cleaned up")
            except Exception as e:
                logger.error("Cleanup error: %s", e)

    cleanup_task = asyncio.create_task(periodic_cleanup())
    yield
    cleanup_task.cancel()


app = FastAPI(title="Develop Backend", version="1.0.0", lifespan=lifespan)


def _get_free_period() -> str:
    """Free tier resets daily. Returns today's date as the period key."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_pro_period() -> str:
    """Pro tier resets monthly. Returns this month as the period key."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _free_reset_time() -> str:
    """ISO8601 timestamp for when the free tier resets (midnight UTC)."""
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if tomorrow <= now:
        from datetime import timedelta
        tomorrow += timedelta(days=1)
    return tomorrow.isoformat()


def _pro_reset_time() -> str:
    """ISO8601 timestamp for when the pro tier resets (1st of next month)."""
    now = datetime.now(timezone.utc)
    if now.month == 12:
        reset = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        reset = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return reset.isoformat()


# ─── POST /api/enhance ───


@app.post("/api/enhance")
async def submit_enhancement(
    image: UploadFile = File(...),
    scene_type: str = Form(default="default"),
    style: str = Form(default="natural"),
    device_id: str = Header(...),
):
    """Accept a photo for enhancement. Returns a job_id immediately."""
    db = await get_db()
    try:
        # Ensure user exists, get their tier
        tier = await ensure_user(db, device_id)

        # Check usage limits
        if tier == "free":
            period = _get_free_period()
            limit = FREE_DAILY_LIMIT
        else:
            period = _get_pro_period()
            limit = PRO_MONTHLY_LIMIT

        used = await get_usage(db, device_id, period)
        if used >= limit:
            resets_at = _free_reset_time() if tier == "free" else _pro_reset_time()
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "limit_reached",
                    "message": "Daily enhancement limit reached" if tier == "free" else "Monthly enhancement limit reached",
                    "resets_at": resets_at,
                },
            )

        # Read the uploaded image
        image_bytes = await image.read()
        if len(image_bytes) == 0:
            raise HTTPException(status_code=400, detail={"error": "empty_image"})

        # Validate scene_type
        valid_scenes = {"portrait", "food", "low_light", "landscape", "indoor", "action", "default"}
        if scene_type not in valid_scenes:
            scene_type = "default"

        # Create job
        job_id = str(uuid.uuid4())
        await create_job(db, job_id, device_id, scene_type, style)

        # Increment usage count
        await increment_usage(db, device_id, period)

        logger.info("Job %s created for device %s (scene=%s)", job_id, device_id[:8], scene_type)

        # Start enhancement in background
        asyncio.create_task(_process_enhancement(job_id, image_bytes, scene_type, style))

        return {"job_id": job_id}

    finally:
        await db.close()


async def _process_enhancement(job_id: str, image_bytes: bytes, scene_type: str, style: str):
    """Background task: call OpenAI and store the result."""
    db = await get_db()
    try:
        image_b64, image_format = await enhance_image(
            openai_client, image_bytes, scene_type, style
        )
        await complete_job(db, job_id, image_b64, image_format)
        logger.info("Job %s completed", job_id)

    except Exception as e:
        error_msg = str(e)
        logger.error("Job %s failed: %s", job_id, error_msg)
        await fail_job(db, job_id, error_msg)

    finally:
        await db.close()


# ─── GET /api/enhance/{job_id} ───


@app.get("/api/enhance/{job_id}")
async def get_enhancement_status(job_id: str, device_id: str = Header(...)):
    """Poll for enhancement result."""
    db = await get_db()
    try:
        job = await get_job(db, job_id)
        if not job:
            raise HTTPException(status_code=404, detail={"error": "job_not_found"})

        response = {"job_id": job["job_id"], "status": job["status"]}

        if job["status"] == "completed":
            response["image_base64"] = job["image_base64"]
            response["image_format"] = job["image_format"]
        elif job["status"] == "failed":
            response["error"] = job["error"]

        return response

    finally:
        await db.close()


# ─── GET /api/usage ───


@app.get("/api/usage")
async def get_usage_info(device_id: str = Header(...)):
    """Check how many enhancements the user has left."""
    db = await get_db()
    try:
        tier = await ensure_user(db, device_id)

        if tier == "free":
            period = _get_free_period()
            limit = FREE_DAILY_LIMIT
            resets_at = _free_reset_time()
        else:
            period = _get_pro_period()
            limit = PRO_MONTHLY_LIMIT
            resets_at = _pro_reset_time()

        used = await get_usage(db, device_id, period)

        return {
            "tier": tier,
            "enhancements_used": used,
            "enhancements_limit": limit,
            "resets_at": resets_at,
        }

    finally:
        await db.close()


# ─── POST /api/webhook/revenuecat ───


@app.post("/api/webhook/revenuecat")
async def revenuecat_webhook(payload: dict):
    """Handle RevenueCat subscription lifecycle events."""
    # Verify webhook authenticity
    if REVENUECAT_WEBHOOK_SECRET:
        auth_key = payload.get("api_key", "")
        if auth_key != REVENUECAT_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    event = payload.get("event", {})
    event_type = event.get("type", "")
    app_user_id = event.get("app_user_id", "")

    if not app_user_id:
        return {"status": "ignored", "reason": "no app_user_id"}

    db = await get_db()
    try:
        # Map RevenueCat events to tier changes
        upgrade_events = {
            "INITIAL_PURCHASE",
            "RENEWAL",
            "PRODUCT_CHANGE",
            "UNCANCELLATION",
        }
        downgrade_events = {
            "CANCELLATION",
            "EXPIRATION",
            "BILLING_ISSUE",
        }

        if event_type in upgrade_events:
            await ensure_user(db, app_user_id)
            await update_user_tier(db, app_user_id, "pro")
            logger.info("User %s upgraded to pro (event=%s)", app_user_id[:8], event_type)
        elif event_type in downgrade_events:
            await update_user_tier(db, app_user_id, "free")
            logger.info("User %s downgraded to free (event=%s)", app_user_id[:8], event_type)

        return {"status": "ok"}

    finally:
        await db.close()


# ─── Health check ───


@app.get("/health")
async def health():
    return {"status": "ok", "service": "develop-backend"}
