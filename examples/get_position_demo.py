"""
使用交易所API获取持仓信息的演示

这个示例展示了新的get_active_position实现：
- 直接从交易所API获取实时持仓数据
- 结合数据库中的策略信息
- 提供API失败时的数据库回退机制
"""

import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.dao import TradeStrategyDAO
from database.manager import DatabaseManager
from config.settings import Config

async def demo_get_active_position():
    """演示获取活跃持仓的新实现"""
    print("=== 获取活跃持仓演示 ===")
    print()
    
    try:
        # 初始化配置和数据库
        config = Config()
        db_manager = DatabaseManager(config.DB_CONFIG)
        dao = TradeStrategyDAO(db_manager)
        
        print("1. 尝试从交易所API获取实时持仓信息...")
        
        # 获取当前持仓
        position = await dao.get_active_position()
        
        if position:
            print("✅ 找到活跃持仓:")
            print(f"   交易对: {position.get('instrument_id', 'N/A')}")
            print(f"   方向: {position['direction']}")
            print(f"   入场价格: {position['entry_price']}")
            print(f"   持仓大小: {position['size']}")
            print(f"   止损价格: {position['stop_loss']}")
            print(f"   止盈价格: {position['take_profit']}")
            print(f"   未实现盈亏: {position.get('unrealized_pnl', 'N/A')}")
            print(f"   保证金: {position.get('margin', 'N/A')}")
            print(f"   标记价格: {position.get('mark_price', 'N/A')}")
            print(f"   策略模式: {position['pattern']}")
            print(f"   入场日期: {position['day']}")
            if position.get('entry_time'):
                print(f"   入场时间: {position['entry_time']}")
        else:
            print("❌ 当前没有活跃持仓")
        
        print()
        print("2. 数据来源说明:")
        print("   - 持仓数据: 直接从交易所API获取（实时）")
        print("   - 策略信息: 从数据库获取（止损、止盈、模式等）")
        print("   - 回退机制: API失败时使用数据库数据")
        
    except Exception as e:
        print(f"❌ 演示过程中发生错误: {str(e)}")
        print("这可能是因为:")
        print("1. 交易所API连接失败")
        print("2. 数据库连接问题")
        print("3. 配置文件缺失")

def compare_old_vs_new():
    """比较新旧实现的差异"""
    print("\n=== 新旧实现对比 ===")
    print()
    
    print("📊 旧实现 (纯数据库):")
    print("   ✅ 优点:")
    print("      - 快速响应")
    print("      - 不依赖外部API")
    print("      - 包含完整策略信息")
    print("   ❌ 缺点:")
    print("      - 数据可能不是最新的")
    print("      - 无法获取实时盈亏")
    print("      - 可能与实际持仓不同步")
    print()
    
    print("🚀 新实现 (API + 数据库):")
    print("   ✅ 优点:")
    print("      - 实时持仓数据")
    print("      - 包含未实现盈亏")
    print("      - 包含保证金信息")
    print("      - 包含标记价格")
    print("      - 结合策略信息")
    print("      - 有回退机制")
    print("   ❌ 缺点:")
    print("      - 依赖API连接")
    print("      - 响应稍慢")
    print("      - 需要处理API错误")

def show_data_structure():
    """展示返回数据结构"""
    print("\n=== 返回数据结构 ===")
    print()
    
    example_data = {
        'direction': 'long',                    # 持仓方向 (long/short)
        'entry_price': 50000.0,                # 入场价格
        'size': 0.1,                           # 持仓大小
        'stop_loss': 48000.0,                  # 止损价格 (来自数据库)
        'take_profit': 52000.0,                # 止盈价格 (来自数据库)
        'entry_time': '2024-01-01 10:00:00',   # 入场时间 (来自数据库)
        'pattern': 'continuous_rise',          # 策略模式 (来自数据库)
        'day': '周一',                         # 入场日期 (来自数据库)
        'instrument_id': 'BTC-USDT-SWAP',      # 交易对 (来自API)
        'unrealized_pnl': 100.0,               # 未实现盈亏 (来自API)
        'margin': 5000.0,                      # 保证金 (来自API)
        'mark_price': 50100.0                  # 标记价格 (来自API)
    }
    
    print("📋 完整数据结构:")
    for key, value in example_data.items():
        source = "(来自API)" if key in ['instrument_id', 'unrealized_pnl', 'margin', 'mark_price'] else "(来自数据库)"
        print(f"   {key}: {value} {source}")

async def main():
    """主函数"""
    print("使用交易所API获取持仓信息演示")
    print("=" * 50)
    
    await demo_get_active_position()
    compare_old_vs_new()
    show_data_structure()
    
    print("\n演示完成！")
    print("\n关键改进:")
    print("1. 实时数据: 直接从交易所获取最新持仓信息")
    print("2. 丰富信息: 包含未实现盈亏、保证金等实时数据")
    print("3. 策略结合: 保留原有的策略信息（止损、止盈等）")
    print("4. 容错机制: API失败时自动回退到数据库查询")
    print("5. 数据一致: 确保持仓数据与交易所同步")

if __name__ == '__main__':
    asyncio.run(main()) 