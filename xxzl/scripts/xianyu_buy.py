"""
闲鱼买入执行脚本
通过 Selenium + 浏览器自动化完成购买流程
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

class XianyuBuyExecutor:
    """闲鱼买入执行器"""
    
    def __init__(self, display_num=':99'):
        self.display_num = display_num
        self.driver = None
        self.result = {
            'status': 'PENDING',
            'item_id': None,
            'order_id': None,
            'error': None,
            'timestamp': datetime.now().isoformat(),
            'screenshot': None
        }
    
    def create_driver(self):
        """创建浏览器驱动"""
        import os
        os.environ['DISPLAY'] = self.display_num
        
        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir=./browser_profiles/xianyu_buy')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_argument('--window-size=1920,1080')
        
        self.driver = uc.Chrome(options=options)
        
        logger.info("✓ 浏览器驱动已创建")
        return self.driver
    
    def buy_item(self, item_id: str, price: float, quantity: int = 1) -> Dict:
        """
        执行购买流程
        
        Args:
            item_id: 商品 ID
            price: 购买价格
            quantity: 数量
        
        Returns:
            执行结果字典
        """
        try:
            self.result['item_id'] = item_id
            
            logger.info(f"开始购买: {item_id}")
            logger.info(f"  价格: ¥{price}")
            logger.info(f"  数量: {quantity}")
            
            # 1. 打开商品页面
            logger.info("\n[步骤 1/5] 打开商品页面...")
            item_url = f'https://2.taobao.com/items/{item_id}'
            self.driver.get(item_url)
            time.sleep(3)
            
            # 2. 点击购买按钮
            logger.info("[步骤 2/5] 点击购买按钮...")
            buy_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//button[contains(text(), "立即购买")]'))
            )
            buy_button.click()
            time.sleep(2)
            
            # 3. 处理购买对话框
            logger.info("[步骤 3/5] 处理购买对话框...")
            
            # 检查是否需要登录
            try:
                login_element = self.driver.find_element(By.XPATH, '//a[contains(text(), "登录")]')
                logger.error("需要登录，中止购买")
                self.result['status'] = 'FAILED'
                self.result['error'] = '需要登录'
                return self.result
            except:
                pass  # 已登录
            
            # 4. 确认订单
            logger.info("[步骤 4/5] 确认订单...")
            confirm_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//button[contains(text(), "确认")]'))
            )
            confirm_button.click()
            time.sleep(3)
            
            # 5. 完成支付（这里假设已���付或使用余额）
            logger.info("[步骤 5/5] 等待订单确认...")
            
            # 等待订单号出现
            order_element = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, '//span[@class="order-id"]'))
            )
            
            order_id = order_element.text
            self.result['order_id'] = order_id
            
            logger.info(f"✓ 购买成功！订单号: {order_id}")
            
            # 截图
            screenshot_path = f'./screenshots/buy_{item_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            self.driver.save_screenshot(screenshot_path)
            self.result['screenshot'] = screenshot_path
            
            self.result['status'] = 'SUCCESS'
            
            return self.result
        
        except Exception as e:
            logger.error(f"购买失败: {e}", exc_info=True)
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
        logger.error("用法: python xianyu_buy.py <item_id> <price> [quantity]")
        print("示例: python xianyu_buy.py 123456789 199.99 1")
        sys.exit(1)
    
    item_id = sys.argv[1]
    price = float(sys.argv[2])
    quantity = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    
    executor = XianyuBuyExecutor()
    executor.create_driver()
    
    result = executor.buy_item(item_id, price, quantity)
    
    # 输出 JSON 结果给后端
    print(executor.to_json())
    
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    sys.exit(main())