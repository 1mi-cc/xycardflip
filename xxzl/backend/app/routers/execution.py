"""
执行 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from app.core.execution_engine import LocalExecutionEngine, ExecutionAction

router = APIRouter(prefix="/api/execution", tags=["execution"])

logger = logging.getLogger(__name__)

class BuyRequest(BaseModel):
    """买入请求"""
    item_id: str
    price: float
    quantity: int = 1

class ListRequest(BaseModel):
    """上架请求"""
    item_id: str
    title: str
    price: float
    description: str = ""

class SellRequest(BaseModel):
    """卖出请求"""
    listing_id: str
    order_id: str
    tracking_number: str = ""

@router.post("/buy")
async def execute_buy(request: BuyRequest):
    """执行买入"""
    result = LocalExecutionEngine.execute_buy(
        request.item_id,
        request.price,
        request.quantity
    )
    
    if result['status'] != 'SUCCESS':
        raise HTTPException(status_code=500, detail=result.get('error'))
    
    return result

@router.post("/list")
async def execute_list(request: ListRequest):
    """执行上架"""
    result = LocalExecutionEngine.execute_list(
        request.item_id,
        request.title,
        request.price,
        request.description
    )
    
    if result['status'] != 'SUCCESS':
        raise HTTPException(status_code=500, detail=result.get('error'))
    
    return result

@router.post("/sell")
async def execute_sell(request: SellRequest):
    """执行卖出"""
    result = LocalExecutionEngine.execute_sell(
        request.listing_id,
        request.order_id,
        request.tracking_number
    )
    
    if result['status'] != 'SUCCESS':
        raise HTTPException(status_code=500, detail=result.get('error'))
    
    return result