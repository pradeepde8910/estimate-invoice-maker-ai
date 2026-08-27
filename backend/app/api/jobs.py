from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from app.api.dependencies import require_roles
from app.models.user import User
from app.services import job_service

router = APIRouter()


@router.post("/api/jobs")
async def create_job(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    generate_brd: bool = Form(True),
    generate_srs: bool = Form(True),
    user: User = Depends(require_roles("Admin", "Developer")),
):
    job_id = await job_service.create_job(file, url, text, generate_brd, generate_srs)
    return {"job_id": job_id}


@router.get("/api/jobs/{job_id}")
async def get_job(job_id: str, user: User = Depends(require_roles("Admin", "Developer", "Finance"))):
    return job_service.get_job_status(job_id)


@router.get("/api/jobs/{job_id}/wait")
async def wait_for_job(
    job_id: str,
    timeout: int = 90,
    user: User = Depends(require_roles("Admin", "Developer", "Finance")),
):
    """
    Synchronously wait for a job to complete.
    Useful for testing tools like JMeter that prefer a single blocking request over polling.
    Will return early if timeout is reached.
    """
    return await job_service.wait_for_job(job_id, timeout)


@router.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user: User = Depends(require_roles("Admin", "Developer"))):
    return job_service.cancel_job(job_id)


@router.get("/api/jobs/{job_id}/document/{doc_type}", response_class=PlainTextResponse)
async def get_job_document(
    job_id: str,
    doc_type: str,
    user: User = Depends(require_roles("Admin", "Developer", "Finance")),
):
    return PlainTextResponse(job_service.get_job_document(job_id, doc_type))
