"""
更新 FastAPI 启动脚本
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
import logging

from app.monitor.pinduoduo_monitor import PinduoduoMonitor
from app.purchase.auto_purchaser import AutoPurchaser
from app.list.fivefish_publisher import FivefishPublisher
from app.fulfillment.auto_fulfillment import AutoFulfillment
from app.orchestration.virtual_product_orchestrator import VirtualProductOrchestrator

logger = logging.getLogger(__name__)

orchestrator: Optional[VirtualProductOrchestrator] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    
    global orchestrator
    
    logger.info("启动虚拟商品自动化系统...")
    
    # 初始化各个组件
    monitor = PinduoduoMonitor()
    purchaser = AutoPurchaser()
    publisher = FivefishPublisher()
    fulfillment = AutoFulfillment()
    
    # 创建编排器
    orchestrator = VirtualProductOrchestrator(
        monitor=monitor,
        purchaser=purchaser,
        publisher=publisher,
        fulfillment=fulfillment
    )
    
    # 启动后台任务
    orchestrator_task = asyncio.create_task(orchestrator.run())
    
    yield
    
    logger.info("关闭系统...")
    orchestrator_task.cancel()

app = FastAPI(title="xycardflip-虚拟商品自动化", lifespan=lifespan)