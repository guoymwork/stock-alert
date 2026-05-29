"""
Annotations (便签) API.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ApiResponse
from app.services.database import Database

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


class AddAnnotationBody(BaseModel):
    symbol: str
    market: str = ""
    time: str = Field(..., description="Chart time, e.g. '2026-05-20' or ISO")
    price: float
    text: str


def _db():
    return Database()


@router.get("/{symbol}", response_model=ApiResponse)
async def list_annotations(symbol: str, market: Optional[str] = None):
    items = _db().get_annotations(symbol)
    return ApiResponse(data=items)


@router.post("", response_model=ApiResponse)
async def create_annotation(body: AddAnnotationBody):
    item = _db().add_annotation(body.symbol, body.market, body.time, body.price, body.text)
    return ApiResponse(data=item)


@router.delete("/{ann_id}", response_model=ApiResponse)
async def remove_annotation(ann_id: int):
    if not _db().delete_annotation(ann_id):
        raise HTTPException(404, "便签不存在")
    return ApiResponse(message="已删除")
