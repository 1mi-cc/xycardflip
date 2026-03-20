"""
虚拟商品配置
"""

VIRTUAL_PRODUCTS = [
    {
        'id': 1,
        'name': 'QQ币100个',
        'category': '游戏点卡',
        'type': 'game_card',
        'official_price': 100,
        'target_buy_discount': 0.03,  # 目标便宜 3%
        'resell_markup': 0.02,         # 卖价加 2%
        'min_margin': 0.01,            # 最小利润率 1%
        'enabled': True,
        'monitor_sources': ['拼多多', '淘宝特价', '京东'],
    },
    {
        'id': 2,
        'name': '梦幻西游点卡1000',
        'category': '游戏点卡',
        'type': 'game_card',
        'official_price': 1000,
        'target_buy_discount': 0.05,
        'resell_markup': 0.03,
        'min_margin': 0.02,
        'enabled': True,
        'monitor_sources': ['拼多多', '淘宝'],
    },
    {
        'id': 3,
        'name': 'QQ会员30天',
        'category': '游戏点卡',
        'type': 'game_card',
        'official_price': 30,
        'target_buy_discount': 0.02,
        'resell_markup': 0.02,
        'min_margin': 0.01,
        'enabled': True,
        'monitor_sources': ['拼多多'],
    },
]

# 监控配置
MONITOR_CONFIG = {
    'pinduoduo': {
        'enabled': True,
        'check_interval_minutes': 5,
        'max_workers': 3,
    },
    'taobao': {
        'enabled': True,
        'check_interval_minutes': 10,
        'max_workers': 2,
    },
}

# 购买配置
PURCHASE_CONFIG = {
    'auto_purchase': True,
    'max_concurrent_purchases': 3,
    'payment_method': 'wallet',  # 使用账户余额
}

# 发布配置
PUBLISH_CONFIG = {
    'auto_list': True,
    'auto_confirm_receipt': True,
    'auto_rate': True,
}

# 监听配置
MONITOR_ORDERS_CONFIG = {
    'check_interval_seconds': 30,
    'auto_send_code': True,
    'auto_confirm_shipment': True,
}