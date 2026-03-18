"""
执行引擎 - 调用本地脚本
"""
import logging
import subprocess
import json
import os
from typing import Dict, Optional
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

class ExecutionAction(Enum):
    """执行动作"""
    BUY = "buy"
    LIST = "list"
    SELL = "sell"

class LocalExecutionEngine:
    """本地执行引擎"""
    
    SCRIPTS_DIR = Path('./scripts')
    
    # 脚本映射
    SCRIPT_MAP = {
        ExecutionAction.BUY: 'xianyu_buy.py',
        ExecutionAction.LIST: 'xianyu_list.py',
        ExecutionAction.SELL: 'xianyu_sell.py',
    }
    
    @classmethod
    def execute_buy(cls, item_id: str, price: float, quantity: int = 1) -> Dict:
        """
        执行买入
        
        调用: python scripts/xianyu_buy.py <item_id> <price> [quantity]
        """
        logger.info(f"[执行] 买入: {item_id} @ ¥{price}")
        
        script_path = cls.SCRIPTS_DIR / cls.SCRIPT_MAP[ExecutionAction.BUY]
        
        cmd = [
            'python',
            str(script_path),
            item_id,
            str(price),
            str(quantity)
        ]
        
        return cls._run_command(cmd, ExecutionAction.BUY)
    
    @classmethod
    def execute_list(cls, item_id: str, title: str, price: float, 
                     description: str = "") -> Dict:
        """
        执行上架
        
        调用: python scripts/xianyu_list.py <item_id> <title> <price> [description]
        """
        logger.info(f"[执行] 上架: {title} @ ¥{price}")
        
        script_path = cls.SCRIPTS_DIR / cls.SCRIPT_MAP[ExecutionAction.LIST]
        
        cmd = [
            'python',
            str(script_path),
            item_id,
            title,
            str(price),
            description
        ]
        
        return cls._run_command(cmd, ExecutionAction.LIST)
    
    @classmethod
    def execute_sell(cls, listing_id: str, order_id: str, 
                    tracking_number: str = "") -> Dict:
        """
        执行卖出
        
        调用: python scripts/xianyu_sell.py <listing_id> <order_id> [tracking_number]
        """
        logger.info(f"[执行] 卖出: {order_id}")
        
        script_path = cls.SCRIPTS_DIR / cls.SCRIPT_MAP[ExecutionAction.SELL]
        
        cmd = [
            'python',
            str(script_path),
            listing_id,
            order_id,
            tracking_number
        ]
        
        return cls._run_command(cmd, ExecutionAction.SELL)
    
    @classmethod
    def _run_command(cls, cmd: list, action: ExecutionAction) -> Dict:
        """
        执行命令并获取结果
        """
        try:
            logger.info(f"执行命令: {' '.join(cmd)}")
            
            # 运行脚本
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 分钟超时
            )
            
            # 解析输出
            if result.returncode == 0:
                try:
                    # 脚本输出 JSON
                    output = result.stdout.strip()
                    if output:
                        execution_result = json.loads(output)
                        logger.info(f"✓ {action.value} 成功: {execution_result}")
                        return execution_result
                except json.JSONDecodeError:
                    logger.error(f"脚本输出非 JSON: {result.stdout}")
                    return {
                        'status': 'FAILED',
                        'error': '脚本输出无效'
                    }
            else:
                logger.error(f"脚本执行失败 (exit code {result.returncode})")
                logger.error(f"stderr: {result.stderr}")
                
                return {
                    'status': 'FAILED',
                    'error': result.stderr or '脚本执行失败'
                }
        
        except subprocess.TimeoutExpired:
            logger.error(f"脚本执行超时")
            return {
                'status': 'TIMEOUT',
                'error': '执行超时（超过 5 分钟）'
            }
        
        except Exception as e:
            logger.error(f"执行异常: {e}", exc_info=True)
            return {
                'status': 'ERROR',
                'error': str(e)
            }