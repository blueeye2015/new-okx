import unittest
import pandas as pd
import sys
import os
from datetime import datetime
from unittest.mock import Mock, MagicMock

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.pattern_strategy import PatternStrategy

class TestPatternLogic(unittest.TestCase):
    """测试修正后的模式逻辑"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建模拟的交易系统
        self.mock_system = Mock()
        self.mock_system.logger = Mock()
        
        # 设置模拟的模式统计数据
        self.mock_system.pattern_stats = {
            '周日': {
                'continuous_rise': {'win_rate': 0.65, 'return_rate': 0.008},
                'continuous_fall': {'win_rate': 0.58, 'return_rate': 0.006}
            },
            '周一': {
                'rise_then_fall': {'win_rate': 0.62, 'return_rate': 0.007}
            }
        }
        
        self.mock_system.volatility_data = {
            '周日': 0.025,
            '周一': 0.030
        }
        
        # 模拟config对象
        self.mock_system.config = Mock()
        self.mock_system.config.RISK_LEVEL = 'medium'
        
        # 创建策略实例
        self.strategy = PatternStrategy(self.mock_system)
    
    def test_pattern_analysis_with_2_points(self):
        """测试2个数据点的模式分析"""
        # 上涨模式
        rising_data = pd.Series([100.0, 105.0])
        pattern = self.strategy.analyze_pattern(rising_data)
        self.assertEqual(pattern, "continuous_rise")
        
        # 下跌模式
        falling_data = pd.Series([105.0, 100.0])
        pattern = self.strategy.analyze_pattern(falling_data)
        self.assertEqual(pattern, "continuous_fall")
    
    def test_should_trade_logic_monday(self):
        """测试周一的交易逻辑（应该查看周日的数据）"""
        # 周一，前一天（周日）是上涨模式
        price_history = pd.Series([100.0, 105.0])  # 上涨模式
        
        should_trade, direction, position_size = self.strategy.should_trade(price_history, 'Monday')
        
        # 应该交易，因为周日的continuous_rise模式胜率65% > 55%
        self.assertTrue(should_trade)
        self.assertEqual(direction, "long")
        self.assertGreater(position_size, 0)
    
    def test_should_trade_logic_tuesday(self):
        """测试周二的交易逻辑（应该查看周一的数据）"""
        # 周二，前一天（周一）是先涨后跌模式
        price_history = pd.Series([100.0, 105.0, 103.0, 101.0])  # rise_then_fall模式
        
        should_trade, direction, position_size = self.strategy.should_trade(price_history, 'Tuesday')
        
        # 应该交易，因为周一的rise_then_fall模式胜率62% > 55%
        self.assertTrue(should_trade)
        self.assertEqual(direction, "long")
        self.assertGreater(position_size, 0)
    
    def test_should_not_trade_insufficient_data(self):
        """测试数据不足时不交易"""
        price_history = pd.Series([100.0])  # 只有1个数据点
        
        should_trade, direction, position_size = self.strategy.should_trade(price_history, 'Monday')
        
        self.assertFalse(should_trade)
        self.assertEqual(direction, "none")
        self.assertEqual(position_size, 0)
    
    def test_should_not_trade_no_pattern_data(self):
        """测试没有对应模式数据时不交易"""
        # 周三，但我们的模拟数据中没有周二的数据
        price_history = pd.Series([100.0, 105.0])
        
        should_trade, direction, position_size = self.strategy.should_trade(price_history, 'Wednesday')
        
        self.assertFalse(should_trade)
        self.assertEqual(direction, "none")
        self.assertEqual(position_size, 0)
    
    def test_weekday_mapping(self):
        """测试星期映射逻辑"""
        # 测试各种星期的映射
        test_cases = [
            ('Monday', '周日'),    # 周一看周日数据
            ('Tuesday', '周一'),   # 周二看周一数据
            ('Wednesday', '周二'), # 周三看周二数据
            ('Thursday', '周三'),  # 周四看周三数据
            ('Friday', '周四'),    # 周五看周四数据
            ('Saturday', '周五'),  # 周六看周五数据
            ('Sunday', '周六'),    # 周日看周六数据
        ]
        
        for current_day, expected_previous_day in test_cases:
            # 创建一个简单的上涨模式
            price_history = pd.Series([100.0, 105.0])
            
            # 添加对应的模式数据
            self.mock_system.pattern_stats[expected_previous_day] = {
                'continuous_rise': {'win_rate': 0.60, 'return_rate': 0.008}
            }
            
            should_trade, _, _ = self.strategy.should_trade(price_history, current_day)
            
            # 验证调用了正确的前一天数据
            # 通过检查日志调用来验证
            debug_calls = [call for call in self.mock_system.logger.debug.call_args_list 
                          if 'Current day:' in str(call)]
            
            if debug_calls:
                last_debug_call = str(debug_calls[-1])
                self.assertIn(f"Previous day: {expected_previous_day}", last_debug_call)

if __name__ == '__main__':
    unittest.main() 