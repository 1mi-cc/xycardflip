"""
闲鱼上架执行脚本
完成商品上架、定价等操作
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

class XianyuListExecutor:
    """闲鱼上架执行器"""
    
    def __init__(self, display_num=':99'):
        self.display_num = display_num
        self.driver = None
        self.result = {
            'status': 'PENDING',
            'item_id': None,
            'listing_id': None,
            'listing_url': None,
            'error': None,
            'timestamp': datetime.now().isoformat(),
            'screenshot': None
        }
    
    def create_driver(self):
        """创建浏览器驱动"""
        import os
        os.environ['DISPLAY'] = self.display_num
        
        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir=./browser_profiles/xianyu_list')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_argument('--window-size=1920,1080')
        
        self.driver = uc.Chrome(options=options)
        
        logger.info("✓ 浏览器驱动已创建")
        return self.driver
    
    def list_item(self, item_id: str, title: str, price: float, 
                  description: str = "", category: str = "卡牌") -> Dict:
        """
        执行上架流程
        
        Args:
            item_id: 原商品 ID（购买时）
            title: 上架标题
            price: 上架价格
            description: 商品描述
            category: 分类
        
        Returns:
            上架结果
        """
        try:
            self.result['item_id'] = item_id
            
            logger.info(f"开始上架: {title}")
            logger.info(f"  价格: ¥{price}")
            logger.info(f"  分类: {category}")
            
            # 1. 进入卖家中心
            logger.info("\n[步骤 1/5] 进入卖家中心...")
            self.driver.get('https://2.taobao.com/my-selling')
            time.sleep(3)
            
            # 2. 点击"发布商品"
            logger.info("[步骤 2/5] 点击发布商品按钮...")
            publish_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//button[contains(text(), "发布")]'))
            )
            publish_button.click()
            time.sleep(2)
            
            # 3. 填写商品信息
            logger.info("[步骤 3/5] 填写商品信息...")
            
            # 标题
            title_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, 'title'))
            )
            title_input.clear()
            title_input.send_keys(title)
            
            # 价格
            price_input = self.driver.find_element(By.NAME, 'price')
            price_input.clear()
            price_input.send_keys(str(price))
            
            # 描述
            if description:
                desc_input = self.driver.find_element(By.NAME, 'description')
                desc_input.clear()
                desc_input.send_keys(description)
            
            time.sleep(2)
            
            # 4. 选择分类
            logger.info("[步骤 4/5] 选择分类...")
            category_select = self.driver.find_element(By.NAME, 'category')
            category_select.send_keys(category)
            time.sleep(1)
            
            # 5. 提交上架
            logger.info("[步骤 5/5] 提交上架...")
            submit_button = self.driver.find_element(By.XPATH, '//button[@type="submit"]')
            submit_button.click()
            
            # 等待上架完成
            time.sleep(3)
            
            # 获取上架链接
            listing_url = self.driver.current_url
            listing_id = listing_url.split('/')[-1] if '/' in listing_url else 'unknown'
            
            self.result['listing_id'] = listing_id
            self.result['listing_url'] = listing_url
            
            logger.info(f"✓ 上架成功！")
            logger.info(f"  链接: {listing_url}")
            
            # 截图
            screenshot_path = f'./screenshots/list_{item_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            self.driver.save_screenshot(screenshot_path)
            self.result['screenshot'] = screenshot_path
            
            self.result['status'] = 'SUCCESS'
            
            return self.result
        
        except Exception as e:
            logger.error(f"上架失败: {e}", exc_info=True)
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
    if len(sys.argv) < 4:
        logger.error("用法: python xianyu_list.py <item_id> <title> <price> [description]")
        print("示例: python xianyu_list.py 123456789 '稀有卡片' 299.99 '全新未开封'")
        sys.exit(1)
    
    item_id = sys.argv[1]
    title = sys.argv[2]
    price = float(sys.argv[3])
    description = sys.argv[4] if len(sys.argv) > 4 else ""
    
    executor = XianyuListExecutor()
    executor.create_driver()
    
    result = executor.list_item(item_id, title, price, description)
    
    # 输出 JSON 结果给后端
    print(executor.to_json())
    
    return 0 if result['status'] == 'SUCCESS' else 1


if __name__ == '__main__':
    sys.exit(main())