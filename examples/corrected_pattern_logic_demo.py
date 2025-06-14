"""
修正后的模式逻辑演示

这个示例展示了修正后的交易逻辑：
- next_day_win_rate 表示前一天的模式对今天的影响
- 如果今天是周一，我们查看周日的模式数据来决定是否交易
- 价格历史数据只需要2个数据点来分析前一天的模式
"""

import pandas as pd
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.pattern_strategy import PatternStrategy
from unittest.mock import Mock

def create_mock_system():
    """创建模拟的交易系统"""
    mock_system = Mock()
    mock_system.logger = Mock()
    
    # 模拟的模式统计数据（来自数据库的 next_day_win_rate）
    mock_system.pattern_stats = {
        '周日': {
            'continuous_rise': {'win_rate': 0.65, 'return_rate': 0.008},  # 周日上涨，周一胜率65%
            'continuous_fall': {'win_rate': 0.58, 'return_rate': 0.006}   # 周日下跌，周一胜率58%
        },
        '周一': {
            'rise_then_fall': {'win_rate': 0.62, 'return_rate': 0.007},   # 周一先涨后跌，周二胜率62%
            'continuous_rise': {'win_rate': 0.45, 'return_rate': -0.002}  # 周一上涨，周二胜率45%（不利）
        },
        '周五': {
            'continuous_rise': {'win_rate': 0.40, 'return_rate': -0.005}  # 周五上涨，周六胜率40%（禁止交易）
        }
    }
    
    mock_system.volatility_data = {
        '周日': 0.025,
        '周一': 0.030,
        '周五': 0.020
    }
    
    mock_system.config = Mock()
    mock_system.config.RISK_LEVEL = 'medium'
    
    return mock_system

def demo_pattern_analysis():
    """演示模式分析"""
    print("=== 模式分析演示 ===")
    
    mock_system = create_mock_system()
    strategy = PatternStrategy(mock_system)
    
    # 测试不同的价格模式
    test_cases = [
        ([100.0, 105.0], "2点上涨"),
        ([105.0, 100.0], "2点下跌"),
        ([100.0, 105.0, 103.0], "3点先涨后跌"),
        ([100.0, 95.0, 102.0], "3点先跌后涨"),
        ([100.0, 105.0, 103.0, 101.0], "4点先涨后跌"),
        ([100.0, 95.0, 98.0, 102.0], "4点先跌后涨")
    ]
    
    for prices, description in test_cases:
        price_series = pd.Series(prices)
        pattern = strategy.analyze_pattern(price_series)
        print(f"{description}: {prices} -> {pattern}")
    
    print()

def demo_trading_logic():
    """演示交易逻辑"""
    print("=== 交易逻辑演示 ===")
    
    mock_system = create_mock_system()
    strategy = PatternStrategy(mock_system)
    
    # 测试不同日期的交易决策
    test_scenarios = [
        ('Monday', [100.0, 105.0], "周一，前一天（周日）上涨"),
        ('Monday', [105.0, 100.0], "周一，前一天（周日）下跌"),
        ('Tuesday', [100.0, 105.0, 103.0, 101.0], "周二，前一天（周一）先涨后跌"),
        ('Tuesday', [100.0, 105.0], "周二，前一天（周一）上涨"),
        ('Saturday', [100.0, 105.0], "周六，前一天（周五）上涨（应该禁止）"),
        ('Wednesday', [100.0, 105.0], "周三，前一天（周二）上涨（无数据）")
    ]
    
    for current_day, prices, description in test_scenarios:
        price_series = pd.Series(prices)
        should_trade, direction, position_size = strategy.should_trade(price_series, current_day)
        
        pattern = strategy.analyze_pattern(price_series)
        
        print(f"{description}")
        print(f"  价格数据: {prices}")
        print(f"  识别模式: {pattern}")
        print(f"  交易决策: {'交易' if should_trade else '不交易'}")
        if should_trade:
            print(f"  方向: {direction}, 仓位: {position_size:.3f}")
        print()

def demo_weekday_mapping():
    """演示星期映射逻辑"""
    print("=== 星期映射逻辑演示 ===")
    
    weekday_mapping = {
        'Monday': '周日',    # 周一看周日数据
        'Tuesday': '周一',   # 周二看周一数据
        'Wednesday': '周二', # 周三看周二数据
        'Thursday': '周三',  # 周四看周三数据
        'Friday': '周四',    # 周五看周四数据
        'Saturday': '周五',  # 周六看周五数据
        'Sunday': '周六',    # 周日看周六数据
    }
    
    print("当前日期 -> 查看的前一天数据:")
    for current, previous in weekday_mapping.items():
        print(f"  {current} -> {previous}")
    
    print("\n逻辑说明:")
    print("- next_day_win_rate 表示前一天的模式对今天的胜率影响")
    print("- 如果今天是周一，我们查看周日的模式统计来预测周一的表现")
    print("- 这样可以利用历史数据中'前一天模式 -> 后一天表现'的关系")
    print()

if __name__ == '__main__':
    print("修正后的比特币交易模式逻辑演示")
    print("=" * 50)
    print()
    
    demo_pattern_analysis()
    demo_trading_logic()
    demo_weekday_mapping()
    
    print("演示完成！")
    print("\n关键改进:")
    print("1. 修正了日期逻辑：当前日期查看前一天的模式数据")
    print("2. 减少了数据需求：只需要2个数据点就能分析模式")
    print("3. 正确理解了next_day_win_rate的含义")
    print("4. 添加了完整的测试覆盖") 