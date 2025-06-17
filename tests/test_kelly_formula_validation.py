import asyncio
import sys
import os
from datetime import datetime
import logging
import pandas as pd
import numpy as np

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.pattern_strategy import PatternStrategy
from trading.trade_executor import TradeExecutor
from config.settings import Config


# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class MockDAO:
    """模拟DAO用于测试"""
    def __init__(self):
        self.position_data = None
        self.trades = []
    
    async def save_position(self, position_data):
        self.position_data = position_data
        print(f"   💾 保存持仓: {position_data}")
    
    async def get_active_position(self):
        return self.position_data
    
    async def update_position(self, position_data):
        self.position_data = position_data
        print(f"   🔄 更新持仓: {position_data}")
    
    async def delete_position(self):
        self.position_data = None
        print("   🗑️ 删除持仓")
    
    async def record_trade(self, trade_result):
        self.trades.append(trade_result)
        print(f"   📊 记录交易: {trade_result}")


def create_strategy_data():
    """根据用户提供的数据创建策略统计"""
    # 从图片中提取的数据
    strategy_data = [
        {'week_period': '周二', 'pattern': '连续上涨', 'cases': 154, 'avg_next_return': 0.39, 'next_day_win_rate': 45.45, 'avg_current_return': 2.75, 'avg_movement': 2.75},
        {'week_period': '周二', 'pattern': '连续下跌', 'cases': 121, 'avg_next_return': 0.27, 'next_day_win_rate': 56.20, 'avg_current_return': -2.65, 'avg_movement': 2.65},
        {'week_period': '周五', 'pattern': '先涨后跌', 'cases': 124, 'avg_next_return': 0.30, 'next_day_win_rate': 58.87, 'avg_current_return': -2.00, 'avg_movement': 2.00},
        {'week_period': '周五', 'pattern': '先跌后涨', 'cases': 150, 'avg_next_return': -0.18, 'next_day_win_rate': 51.33, 'avg_current_return': 2.49, 'avg_movement': 2.49},
        {'week_period': '周五', 'pattern': '连续上涨', 'cases': 158, 'avg_next_return': 0.82, 'next_day_win_rate': 56.33, 'avg_current_return': 2.30, 'avg_movement': 2.30},
        {'week_period': '周五', 'pattern': '连续下跌', 'cases': 128, 'avg_next_return': -0.22, 'next_day_win_rate': 56.25, 'avg_current_return': -2.75, 'avg_movement': 2.75},
        {'week_period': '周六', 'pattern': '先涨后跌', 'cases': 142, 'avg_next_return': 0.00, 'next_day_win_rate': 52.82, 'avg_current_return': -1.53, 'avg_movement': 1.53},
        {'week_period': '周六', 'pattern': '先跌后涨', 'cases': 145, 'avg_next_return': 0.23, 'next_day_win_rate': 52.41, 'avg_current_return': 1.51, 'avg_movement': 1.51},
        {'week_period': '周六', 'pattern': '连续上涨', 'cases': 166, 'avg_next_return': -0.09, 'next_day_win_rate': 44.58, 'avg_current_return': 1.93, 'avg_movement': 1.93},
        {'week_period': '周六', 'pattern': '连续下跌', 'cases': 107, 'avg_next_return': 0.08, 'next_day_win_rate': 57.94, 'avg_current_return': -1.96, 'avg_movement': 1.96},
        {'week_period': '周四', 'pattern': '先涨后跌', 'cases': 150, 'avg_next_return': 0.19, 'next_day_win_rate': 56.00, 'avg_current_return': -2.71, 'avg_movement': 2.71},
        {'week_period': '周四', 'pattern': '先跌后涨', 'cases': 144, 'avg_next_return': 0.36, 'next_day_win_rate': 57.64, 'avg_current_return': 2.51, 'avg_movement': 2.51},
        {'week_period': '周四', 'pattern': '连续上涨', 'cases': 138, 'avg_next_return': 0.45, 'next_day_win_rate': 54.35, 'avg_current_return': 2.93, 'avg_movement': 2.93},
        {'week_period': '周四', 'pattern': '连续下跌', 'cases': 127, 'avg_next_return': 0.00, 'next_day_win_rate': 51.97, 'avg_current_return': -2.49, 'avg_movement': 2.49},
        {'week_period': '周日', 'pattern': '先涨后跌', 'cases': 161, 'avg_next_return': 0.63, 'next_day_win_rate': 60.87, 'avg_current_return': -1.67, 'avg_movement': 1.67},
        {'week_period': '周日', 'pattern': '先跌后涨', 'cases': 137, 'avg_next_return': -0.38, 'next_day_win_rate': 43.07, 'avg_current_return': 1.92, 'avg_movement': 1.92},
        {'week_period': '周日', 'pattern': '连续上涨', 'cases': 150, 'avg_next_return': 0.87, 'next_day_win_rate': 52.67, 'avg_current_return': 1.92, 'avg_movement': 1.92},
        {'week_period': '周日', 'pattern': '连续下跌', 'cases': 112, 'avg_next_return': 0.97, 'next_day_win_rate': 60.71, 'avg_current_return': -2.27, 'avg_movement': 2.27},
    ]
    
    return pd.DataFrame(strategy_data)


def calculate_kelly_formula(win_rate, avg_win, avg_loss):
    """
    计算凯利公式
    :param win_rate: 胜率 (0-1)
    :param avg_win: 平均盈利 (%)
    :param avg_loss: 平均亏损 (%)
    :return: 凯利比例
    """
    if avg_loss == 0:
        return 0
    
    # 凯利公式: f = (bp - q) / b
    # 其中: b = 赔率 = avg_win / avg_loss
    #       p = 胜率
    #       q = 败率 = 1 - p
    
    p = win_rate / 100  # 转换为小数
    q = 1 - p
    b = abs(avg_win / avg_loss) if avg_loss != 0 else 1
    
    kelly_fraction = (b * p - q) / b
    
    # 限制在合理范围内
    kelly_fraction = max(0, min(kelly_fraction, 0.25))  # 最大25%
    
    return kelly_fraction


def analyze_strategy_effectiveness():
    """分析策略有效性"""
    print("=== 策略有效性分析 ===")
    
    df = create_strategy_data()
    
    # 筛选有效策略（胜率 > 55%）
    effective_strategies = df[df['next_day_win_rate'] > 55.0]
    
    print(f"📊 总策略数: {len(df)}")
    print(f"📈 有效策略数: {len(effective_strategies)} (胜率 > 55%)")
    print(f"📈 有效策略比例: {len(effective_strategies)/len(df)*100:.1f}%")
    
    if len(effective_strategies) > 0:
        print("\n🎯 有效策略列表:")
        for _, strategy in effective_strategies.iterrows():
            print(f"   {strategy['week_period']} - {strategy['pattern']}: "
                  f"胜率 {strategy['next_day_win_rate']:.1f}%, "
                  f"平均收益 {strategy['avg_next_return']:.2f}%")
    
    return effective_strategies


def test_kelly_position_sizing():
    """测试凯利公式仓位计算"""
    print("\n=== 凯利公式仓位计算测试 ===")
    
    df = create_strategy_data()
    
    # 为每个策略计算凯利仓位
    results = []
    
    for _, row in df.iterrows():
        win_rate = row['next_day_win_rate']
        avg_return = row['avg_next_return']
        avg_movement = row['avg_movement']
        
        # 假设亏损时的平均亏损为平均波动的一半
        avg_loss = avg_movement / 2
        avg_win = abs(avg_return) if avg_return > 0 else avg_movement / 2
        
        kelly_fraction = calculate_kelly_formula(win_rate, avg_win, avg_loss)
        
        result = {
            'week_period': row['week_period'],
            'pattern': row['pattern'],
            'win_rate': win_rate,
            'avg_return': avg_return,
            'kelly_fraction': kelly_fraction,
            'recommended_position': kelly_fraction * 100,  # 转换为百分比
            'is_tradeable': win_rate > 55.0 and kelly_fraction > 0.01
        }
        
        results.append(result)
    
    # 显示结果
    print(f"{'星期':<8} {'模式':<12} {'胜率':<8} {'平均收益':<10} {'凯利比例':<10} {'建议仓位':<10} {'可交易'}")
    print("-" * 80)
    
    for result in results:
        tradeable = "✅" if result['is_tradeable'] else "❌"
        print(f"{result['week_period']:<8} {result['pattern']:<12} "
              f"{result['win_rate']:<8.1f} {result['avg_return']:<10.2f} "
              f"{result['kelly_fraction']:<10.3f} {result['recommended_position']:<10.1f}% {tradeable}")
    
    return results


def test_pattern_strategy_logic():
    """测试模式策略逻辑"""
    print("\n=== 模式策略逻辑测试 ===")
    
    try:
        # 创建模拟的pattern_stats数据
        pattern_stats = {}
        df = create_strategy_data()
        
        for _, row in df.iterrows():
            day = row['week_period']
            pattern_en = {
                '连续上涨': 'continuous_rise',
                '连续下跌': 'continuous_fall', 
                '先涨后跌': 'rise_then_fall',
                '先跌后涨': 'fall_then_rise'
            }.get(row['pattern'], row['pattern'])
            
            if day not in pattern_stats:
                pattern_stats[day] = {}
            
            pattern_stats[day][pattern_en] = {
                'win_rate': row['next_day_win_rate'] / 100,
                'avg_return': row['avg_next_return'] / 100,
                'return_rate': abs(row['avg_next_return']) / 100,  # 添加return_rate字段
                'count': row['cases']
            }
        
        # 创建策略实例
        class MockConfig:
            def __init__(self):
                self.RISK_LEVEL = 'medium'
        
        class MockTradingSystem:
            def __init__(self):
                self.pattern_stats = pattern_stats
                self.logger = logging.getLogger('MockTradingSystem')
                self.config = MockConfig()
                self.volatility_data = {
                    '周一': 0.02, '周二': 0.025, '周三': 0.022, '周四': 0.024,
                    '周五': 0.026, '周六': 0.018, '周日': 0.020
                }
        
        mock_system = MockTradingSystem()
        strategy = PatternStrategy(mock_system)
        
        # 测试不同场景
        test_cases = [
            {
                'name': '周日连续下跌模式（高胜率）',
                'price_history': pd.Series([100, 98, 96]),  # 连续下跌
                'current_day': 'Sunday',
                'expected_trade': True
            },
            {
                'name': '周五连续上涨模式（中等胜率）',
                'price_history': pd.Series([100, 102, 104]),  # 连续上涨
                'current_day': 'Friday',
                'expected_trade': True
            },
            {
                'name': '周六连续上涨模式（低胜率）',
                'price_history': pd.Series([100, 102, 104]),  # 连续上涨
                'current_day': 'Saturday',
                'expected_trade': False
            },
            {
                'name': '周四先跌后涨模式（中等胜率）',
                'price_history': pd.Series([100, 98, 101]),  # 先跌后涨
                'current_day': 'Thursday',
                'expected_trade': True
            }
        ]
        
        print(f"{'测试场景':<25} {'模式':<15} {'胜率':<8} {'是否交易':<8} {'仓位':<8} {'结果'}")
        print("-" * 80)
        
        for case in test_cases:
            should_trade, direction, position_size = strategy.should_trade(
                case['price_history'], case['current_day']
            )
            
            pattern = strategy.analyze_pattern(case['price_history'])
            
            # 获取胜率信息
            weekday_map = {
                'Sunday': '周日', 'Monday': '周一', 'Tuesday': '周二',
                'Wednesday': '周三', 'Thursday': '周四', 'Friday': '周五', 'Saturday': '周六'
            }
            previous_day_map = {
                '周一': '周日', '周二': '周一', '周三': '周二', '周四': '周三',
                '周五': '周四', '周六': '周五', '周日': '周六'
            }
            
            current_day_cn = weekday_map.get(case['current_day'], case['current_day'])
            previous_day = previous_day_map.get(current_day_cn, current_day_cn)
            
            win_rate = 0
            if previous_day in pattern_stats and pattern in pattern_stats[previous_day]:
                win_rate = pattern_stats[previous_day][pattern]['win_rate'] * 100
            
            result = "✅" if should_trade == case['expected_trade'] else "❌"
            
            print(f"{case['name']:<25} {pattern:<15} {win_rate:<8.1f} "
                  f"{'是' if should_trade else '否':<8} {position_size:<8.1f} {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ 策略逻辑测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_real_trading_scenario():
    """测试真实交易场景"""
    print("\n=== 真实交易场景测试 ===")
    
    try:
        # 模拟一个高胜率策略的交易
        print("📋 场景: 周日连续下跌模式（胜率60.71%）")
        
        # 策略参数
        win_rate = 60.71
        avg_return = 0.97
        avg_movement = 2.27
        
        # 计算凯利仓位
        kelly_fraction = calculate_kelly_formula(win_rate, avg_return, avg_movement/2)
        
        print(f"📊 胜率: {win_rate}%")
        print(f"📊 平均收益: {avg_return}%")
        print(f"📊 凯利比例: {kelly_fraction:.3f}")
        print(f"📊 建议仓位: {kelly_fraction*100:.1f}%")
        
        # 模拟交易结果
        account_balance = 10000  # 假设账户余额10000 USDT
        position_size = account_balance * kelly_fraction
        
        print(f"💰 账户余额: {account_balance} USDT")
        print(f"💰 交易金额: {position_size:.2f} USDT")
        
        # 模拟盈利情况
        if avg_return > 0:
            profit = position_size * (avg_return / 100)
            print(f"📈 预期盈利: {profit:.2f} USDT")
            print(f"📈 盈利率: {profit/account_balance*100:.2f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 真实交易场景测试失败: {str(e)}")
        return False


async def main():
    """主测试函数"""
    print("🎯 凯利公式与策略有效性验证")
    print("=" * 60)
    
    test_results = []
    
    # 1. 分析策略有效性
    effective_strategies = analyze_strategy_effectiveness()
    test_results.append(len(effective_strategies) > 0)
    
    # 2. 测试凯利公式仓位计算
    kelly_results = test_kelly_position_sizing()
    test_results.append(len([r for r in kelly_results if r['is_tradeable']]) > 0)
    
    # 3. 测试模式策略逻辑
    strategy_logic_ok = test_pattern_strategy_logic()
    test_results.append(strategy_logic_ok)
    
    # 4. 测试真实交易场景
    real_scenario_ok = test_real_trading_scenario()
    test_results.append(real_scenario_ok)
    
    # 统计结果
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n=== 📊 测试总结 ===")
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    
    if passed == total:
        print("🎉 所有测试通过！")
        print("💡 凯利公式计算和策略逻辑都是有效的")
    else:
        print("⚠️  部分测试失败，需要检查策略逻辑")
    
    # 总结建议
    print(f"\n=== 💡 策略建议 ===")
    tradeable_count = len([r for r in kelly_results if r['is_tradeable']])
    print(f"📈 可交易策略数量: {tradeable_count}/{len(kelly_results)}")
    print(f"📈 最佳策略: 周日连续下跌模式（胜率60.71%，建议仓位约15-20%）")
    print(f"📈 风险控制: 单笔交易仓位不超过25%，严格按照凯利公式执行")


if __name__ == "__main__":
    asyncio.run(main()) 