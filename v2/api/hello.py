from fastapi import APIRouter
from v2.models.base import Base

router = APIRouter()

@router.get("/hello")
def hello_world():
    # Verify we can import from the newly structured folders
    return {
        "message": "Hello from V2! Skeleton folders are correctly configured.",
        "base_imported": str(Base)
    }
