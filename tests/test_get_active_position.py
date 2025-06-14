"""
测试使用交易所API获取持仓信息的新实现
"""

import unittest
import asyncio
import sys
import os
from unittest.mock import Mock, patch, AsyncMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.dao import TradeStrategyDAO
from database.manager import DatabaseManager

class TestGetActivePosition(unittest.TestCase):
    """测试新的get_active_position实现"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的数据库管理器
        self.mock_db_manager = Mock(spec=DatabaseManager)
        self.dao = TradeStrategyDAO(self.mock_db_manager)
    
    @patch('exchange.base.ExchangeBase')
    def test_get_active_position_with_real_position(self, mock_exchange_class):
        """测试有实际持仓时的情况"""
        # 模拟交易所返回的数据
        mock_exchange = Mock()
        mock_exchange_class.return_value = mock_exchange
        
        mock_exchange.get_account_info.return_value = {
            'positions': {
                'data': [
                    {
                        'instId': 'BTC-USDT-SWAP',
                        'pos': '0.1',  # 持仓量
                        'avgPx': '50000.0',  # 平均价格
                        'upl': '100.0',  # 未实现pnl
                        'margin': '5000.0',  # 保证金
                        'markPx': '50100.0'  # 标记价格
                    }
                ]
            },
            'balance': 10000.0
        }
        
        # 模拟数据库返回的策略信息
        async def mock_get_strategy_info(instrument_id):
            return {
                'stop_loss': 48000.0,
                'take_profit': 52000.0,
                'entry_time': '2024-01-01 10:00:00',
                'pattern': 'continuous_rise',
                'day': '周一'
            }
        
        self.dao._get_position_strategy_info = AsyncMock(side_effect=mock_get_strategy_info)
        
        # 运行测试
        async def run_test():
            result = await self.dao.get_active_position()
            
            # 验证结果
            self.assertIsNotNone(result)
            self.assertEqual(result['direction'], 'long')
            self.assertEqual(result['entry_price'], 50000.0)
            self.assertEqual(result['size'], 0.1)
            self.assertEqual(result['stop_loss'], 48000.0)
            self.assertEqual(result['take_profit'], 52000.0)
            self.assertEqual(result['pattern'], 'continuous_rise')
            self.assertEqual(result['day'], '周一')
            self.assertEqual(result['instrument_id'], 'BTC-USDT-SWAP')
            self.assertEqual(result['unrealized_pnl'], 100.0)
            self.assertEqual(result['margin'], 5000.0)
            self.assertEqual(result['mark_price'], 50100.0)
        
        asyncio.run(run_test())
    
    @patch('exchange.base.ExchangeBase')
    def test_get_active_position_no_position(self, mock_exchange_class):
        """测试没有持仓时的情况"""
        # 模拟交易所返回的数据（无持仓）
        mock_exchange = Mock()
        mock_exchange_class.return_value = mock_exchange
        
        mock_exchange.get_account_info.return_value = {
            'positions': {
                'data': [
                    {
                        'instId': 'BTC-USDT-SWAP',
                        'pos': '0',  # 无持仓
                        'avgPx': '0',
                        'upl': '0',
                        'margin': '0',
                        'markPx': '50000.0'
                    }
                ]
            },
            'balance': 10000.0
        }
        
        # 运行测试
        async def run_test():
            result = await self.dao.get_active_position()
            
            # 验证结果
            self.assertIsNone(result)
        
        asyncio.run(run_test())
    
    @patch('exchange.base.ExchangeBase')
    def test_get_active_position_short_position(self, mock_exchange_class):
        """测试空头持仓的情况"""
        # 模拟交易所返回的数据
        mock_exchange = Mock()
        mock_exchange_class.return_value = mock_exchange
        
        mock_exchange.get_account_info.return_value = {
            'positions': {
                'data': [
                    {
                        'instId': 'BTC-USDT-SWAP',
                        'pos': '-0.05',  # 空头持仓
                        'avgPx': '51000.0',
                        'upl': '-50.0',
                        'margin': '2500.0',
                        'markPx': '50900.0'
                    }
                ]
            },
            'balance': 10000.0
        }
        
        # 模拟数据库返回的策略信息
        async def mock_get_strategy_info(instrument_id):
            return {
                'stop_loss': 52000.0,
                'take_profit': 49000.0,
                'entry_time': '2024-01-01 14:00:00',
                'pattern': 'fall_then_rise',
                'day': '周二'
            }
        
        self.dao._get_position_strategy_info = AsyncMock(side_effect=mock_get_strategy_info)
        
        # 运行测试
        async def run_test():
            result = await self.dao.get_active_position()
            
            # 验证结果
            self.assertIsNotNone(result)
            self.assertEqual(result['direction'], 'short')
            self.assertEqual(result['entry_price'], 51000.0)
            self.assertEqual(result['size'], 0.05)  # 绝对值
            self.assertEqual(result['stop_loss'], 52000.0)
            self.assertEqual(result['take_profit'], 49000.0)
            self.assertEqual(result['pattern'], 'fall_then_rise')
            self.assertEqual(result['day'], '周二')
            self.assertEqual(result['unrealized_pnl'], -50.0)
        
        asyncio.run(run_test())
    
    @patch('exchange.base.ExchangeBase')
    def test_get_active_position_api_failure_fallback(self, mock_exchange_class):
        """测试API调用失败时的回退机制"""
        # 模拟API调用失败
        mock_exchange = Mock()
        mock_exchange_class.return_value = mock_exchange
        mock_exchange.get_account_info.side_effect = Exception("API调用失败")
        
        # 模拟数据库回退方法
        async def mock_fallback():
            return {
                'direction': 'long',
                'entry_price': 49000.0,
                'size': 0.2,
                'stop_loss': 47000.0,
                'take_profit': 51000.0,
                'entry_time': '2024-01-01 09:00:00',
                'pattern': 'continuous_fall',
                'day': '周日'
            }
        
        self.dao._get_active_position_from_db = AsyncMock(side_effect=mock_fallback)
        
        # 运行测试
        async def run_test():
            result = await self.dao.get_active_position()
            
            # 验证结果（应该使用回退数据）
            self.assertIsNotNone(result)
            self.assertEqual(result['direction'], 'long')
            self.assertEqual(result['entry_price'], 49000.0)
            self.assertEqual(result['pattern'], 'continuous_fall')
            self.assertEqual(result['day'], '周日')
        
        asyncio.run(run_test())
    
    @patch('exchange.base.ExchangeBase')
    def test_get_active_position_no_strategy_info(self, mock_exchange_class):
        """测试没有策略信息时的情况"""
        # 这个测试验证当数据库中没有策略信息时，系统能正常处理
        
        # 模拟交易所返回的数据
        mock_exchange = Mock()
        mock_exchange_class.return_value = mock_exchange
        
        mock_exchange.get_account_info.return_value = {
            'positions': {
                'data': [
                    {
                        'instId': 'ETH-USDT-SWAP',
                        'pos': '1.0',
                        'avgPx': '3000.0',
                        'upl': '50.0',
                        'margin': '1500.0',
                        'markPx': '3050.0'
                    }
                ]
            },
            'balance': 10000.0
        }
        
        # 模拟没有策略信息
        self.dao._get_position_strategy_info = AsyncMock(return_value=None)
        
        # 运行测试
        async def run_test():
            result = await self.dao.get_active_position()
            
            # 验证结果（应该使用默认值）
            self.assertIsNotNone(result)
            self.assertEqual(result['direction'], 'long')
            self.assertEqual(result['entry_price'], 3000.0)
            self.assertEqual(result['size'], 1.0)
            self.assertEqual(result['stop_loss'], 0)  # 默认值
            self.assertEqual(result['take_profit'], 0)  # 默认值
            self.assertEqual(result['pattern'], 'unknown')  # 默认值
            self.assertEqual(result['day'], 'unknown')  # 默认值
            self.assertEqual(result['instrument_id'], 'ETH-USDT-SWAP')
        
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main() 