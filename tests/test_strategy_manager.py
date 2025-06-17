import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.strategy_manager import StrategyManager
from database.dao import TradeStrategyDAO
from database.manager import DatabaseManager
from exchange.base import ExchangeBase
from config.settings import Config


class MockConfig:
    """模拟配置类用于测试"""
    def __init__(self):
        self.TRADING_SYMBOL = "BTC-USDT-SWAP"
        self.IS_SIMULATED = True
        self.DB_CONFIG = {
            'host': 'localhost',
            'port': 5432,
            'database': 'market_data',
            'username': 'postgres',
            'password': '12'
        }


class MockExchangeBase:
    """模拟交易所接口用于测试"""
    def get_balance(self):
        return 1000.0  # 模拟余额


class MockDAO:
    """模拟DAO用于测试"""
    async def get_pattern_stats_from_table(self):
        # 返回模拟的模式统计数据
        return [
            {
                'week_period': '周一',
                'pattern': 'rise_then_fall',
                'next_day_win_rate': 60.0,
                'avg_next_return': 2.5,
                'cases': 100,
                'avg_movement': 3.0
            },
            {
                'week_period': '周一',
                'pattern': 'continuous_rise',
                'next_day_win_rate': 55.0,
                'avg_next_return': 1.8,
                'cases': 80,
                'avg_movement': 2.5
            }
        ]
    
    async def refresh_model_data(self):
        pass
    
    async def get_funding_cost_data(self, symbol, hours):
        # 返回模拟的资金费率数据
        return [
            {
                'fundingTime': datetime.now(),
                'fundingRate': 0.0001,
                'realizedRate': 0.0001,
                'method': 'next_funding_time'
            }
        ]


async def test_strategy_manager():
    """测试策略管理器"""
    print("=== 测试策略管理器 ===")
    
    # 创建模拟对象
    config = MockConfig()
    dao = MockDAO()
    exchange_base = MockExchangeBase()
    
    # 创建策略管理器
    strategy_manager = StrategyManager(config, dao, exchange_base)
    
    try:
        # 测试初始化
        print("1. 测试策略初始化...")
        await strategy_manager.initialize_strategy()
        print(f"   策略是否准备就绪: {strategy_manager.is_strategy_ready()}")
        
        # 测试策略统计信息
        print("2. 测试策略统计信息...")
        stats = strategy_manager.get_strategy_stats()
        print(f"   模式数量: {stats['patterns_count']}")
        print(f"   覆盖天数: {stats['days_covered']}")
        
        # 测试交易信号生成
        print("3. 测试交易信号生成...")
        # 创建模拟价格历史
        price_history = pd.Series([50000, 50100], 
                                 index=pd.date_range('2024-01-01', periods=2, freq='D'))
        
        signal = await strategy_manager.generate_trade_signal(50000, 'Monday', price_history)
        print(f"   交易信号: {signal}")
        
        # 测试资金费率计算
        print("4. 测试资金费率计算...")
        funding_info = await strategy_manager.calculate_funding_cost("BTC-USDT-SWAP", 1000, 24)
        print(f"   资金费率信息: {funding_info}")
        
        # 测试风险参数
        print("5. 测试风险参数...")
        risk_params = strategy_manager.get_risk_parameters('conservative')
        print(f"   保守风险参数: {risk_params}")
        
        print("✅ 策略管理器测试完成")
        
    except Exception as e:
        print(f"❌ 策略管理器测试失败: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_strategy_manager()) 