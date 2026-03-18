"""
闲鱼卖出执行脚本
处理已成交订单、确认交付等
"""
import logging
import json
import time
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class XianyuSellExecutor:
    """闲鱼卖出执行器"""
    
    def __init__(self, display_num=':99'):
        self.display_num = display_num
        self.driver = None
        self.result = {
            'status': 'PENDING',
            'listing_id': None,
            'order_id': None,
            'sale_amount': 0,
            'error': None,
            'timestamp': datetime.now().isoformat(),
            'screenshot': None
        }
    
    def create_driver(self):
        """创建浏览器驱动"""
        import os
        os.environ['DISPLAY'] = self.display_num
        
        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir=./browser_profiles/xianyu_sell')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_argument('--window-size=1920,1080')
        
        self.driver = uc.Chrome(options=options)
        
        logger.info("✓ 浏览器驱动已创建")
        return self.driver
    
    def complete_sale(self, listing_id: str, order_id: str, 
                     tracking_number: str = "", delivery_method: str = "自送") -> Dict:
        """
        执行卖出完成流程
        
        Args:
            listing_id: 上架商品 ID
            order_id: 交易订单号
            tracking_number: 物流单号
            delivery_method: 交付方式（自送/邮寄等）
        
        Returns:
            卖出结果
        """
        try:
            self.result['listing_id'] = listing_id
            self.result['order_id'] = order_id
            
            logger.info(f"开始处理卖出: {order_id}")
            logger.info(f"  上架ID: {listing_id}")
            logger.info(f"  交付方式: {delivery_method}")
            
            # 1. 进入订单详情
            logger.info("\n[步骤 1/4] 打开订单页面...")
            order_url = f'https://2.taobao.com/orders/{order_id}'
            self.driver.get(order_url)
            time.sleep(3)
            
            # 2. 确认收款
            logger.info("[步骤 2/4] 确认收款...")
            confirm_payment_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//button[contains(text(), "确认收款")]'))
            )
            
            # 检查是否已收款
            try:
                payment_status = self.driver.find_element(By.XPATH, '//span[contains(text(), "已收款")]')
                logger.info("✓ 已确认收款")
            except:
                confirm_payment_button.click()
                time.sleep(2)
            
            # 3. 确认发货（如果需要邮寄）
            logger.info("[步骤 3/4] 处理发货...")
            
            if delivery_method == "邮寄" and tracking_number:
                try:
                    tracking_input = self.driver.find_element(By.NAME, 'tracking_number')
                    tracking_input.clear()
                    tracking_input.send_keys(tracking_number)
                    
                    confirm_shipping = self.driver.find_element(By.XPATH, '//button[contains(text(), "确认发货")]')
                    confirm_shipping.click()
                    time.sleep(2)
                except:
                    logger.warning("⚠️  未找到发货信息")
            
            # 4. 获取收款金额
            logger.info("[步骤 4/4] 获取交易信息...")
            
            try:
                amount_element = self.driver.find_element(By.XPATH, '//span[@class="amount"]')
                amount_text = amount_element.text
                # 提取数字
                import re
                match = re.search(r'¥([\d.]+)', amount_text)
                if match:
                    self.result['sale_amount'] = float(match.group(1))
            except:
                logger.warning("⚠️  未获取到交易金额")
            
            logger.info(f"✓ 卖出成功！")
            logger.info(f"  金额: ¥{self.result['sale_amount']}")
            
            # 截图
            screenshot_path = f'./screenshots/sell_{listing_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            self.driver.save_screenshot(screenshot_path)
            self.result['screenshot'] = screenshot_path
            
            self.result['status'] = 'SUCCESS'
            
            return self.result
        
        except Exception as e:
            logger.error(f"卖出失败: {e}", exc_info=True)
            self.result['status'] = 'FAILED'
            self.result['error'] = str(e)
            return self.result
        
        finally:
            if self.driver:
                self.driver.quit()
    
    def to_json(self) -> str:
        """输出为 JSON"""
        return json.dumps(self.result, ensure_ascii=False, indent=2)


def main():
    """主函数"""
    if len(sys.argv) < 3:
        logger.error("用法: python xianyu_sell.py <listing_id> <order_id> [tracking_number]")
        print("示例: python xianyu_sell.py 123456789 987654321 SF123456789")
        sys.exit(1)
    
    listing_id = sys.argv[1]
    order_id = sys.argv[2]
    tracking_number = sys.argv[3] if len(sys.argv) > 3 else ""
    
    executor = XianyuSellExecutor()
    executor.create_driver()
    
    result = executor.complete_sale(listing_id, order_id, tracking_number)
    
    # 输出 JSON 结果给后端
    print(executor.to_json())
    
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    sys.exit(main())