import asyncio
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.trade_executor import TradeExecutor
from database.dao import TradeStrategyDAO
from config.settings import Config


class MockConfig:
    """模拟配置类用于测试"""
    def __init__(self):
        self.TRADING_SYMBOL = "BTC-USDT-SWAP"
        self.IS_SIMULATED = True


class MockDAO:
    """模拟DAO用于测试"""
    def __init__(self):
        self.position_data = None
    
    async def save_position(self, position_data):
        self.position_data = position_data
        print(f"   保存持仓: {position_data}")
    
    async def get_active_position(self):
        return self.position_data
    
    async def update_position(self, position_data):
        self.position_data = position_data
        print(f"   更新持仓: {position_data}")
    
    async def delete_position(self):
        self.position_data = None
        print("   删除持仓")
    
    async def record_trade(self, trade_result):
        print(f"   记录交易: {trade_result}")


class MockOrderManager:
    """模拟下单管理器"""
    def place_order(self, instrument_id, order_type, side, price, size):
        return {
            'order_id': '12345',
            'status': 'filled',
            'filled_size': size,
            'avg_price': price
        }


# 模拟下单模块
class MockPlaceOrderModule:
    class OkexOrderManager:
        def __init__(self, is_simulated=True):
            self.is_simulated = is_simulated
        
        def place_order(self, instrument_id, order_type, side, price, size):
            return MockOrderManager().place_order(instrument_id, order_type, side, price, size)


async def test_trade_executor():
    """测试交易执行器"""
    print("=== 测试交易执行器 ===")
    
    # 创建模拟对象
    config = MockConfig()
    dao = MockDAO()
    
    # 创建交易执行器
    trade_executor = TradeExecutor(config, dao)
    
    # 模拟下单模块
    import sys
    sys.modules['trade.place_order'] = MockPlaceOrderModule()
    
    try:
        # 测试开仓
        print("1. 测试开仓操作...")
        trade_signal = {
            'direction': 'long',
            'entry_price': 1049432,
            'trade_amount': 0.1,
            'btc_amount': 0.02,
            'stop_loss': 1040432,
            'take_profit': 52000,
            'pattern': 'rise_then_fall',
            'day': 'Monday',
            'funding_info': {'cost_percentage': 0.1}
        }
        
        open_result = await trade_executor.open_position(trade_signal)
        print(f"   开仓结果: {open_result}")
        
        # 测试获取当前持仓
        print("2. 测试获取当前持仓...")
        position = await trade_executor.get_current_position()
        print(f"   当前持仓: {position}")
        
        # 测试计算盈亏
        print("3. 测试计算持仓盈亏...")
        pnl_info = await trade_executor.calculate_position_pnl(1049432)
        print(f"   盈亏信息: {pnl_info}")
        
        # 测试更新止损止盈
        print("4. 测试更新止损止盈...")
        if position:
            update_result = await trade_executor.update_position_stops(position, 1029432, 1079432)
            print(f"   更新结果: {update_result}")
        
        # 测试平仓
        print("5. 测试平仓操作...")
        close_signal = {
            'exit_price': 1049432,
            'reason': 'take_profit'
        }
        
        close_result = await trade_executor.close_position(close_signal)
        print(f"   平仓结果: {close_result}")
        
        # 测试平仓后获取持仓
        print("6. 测试平仓后获取持仓...")
        position_after_close = await trade_executor.get_current_position()
        print(f"   平仓后持仓: {position_after_close}")
        
        print("✅ 交易执行器测试完成")
        
    except Exception as e:
        print(f"❌ 交易执行器测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_order_execution():
    """测试下单执行"""
    print("\n=== 测试下单执行 ===")
    
    config = MockConfig()
    dao = MockDAO()
    trade_executor = TradeExecutor(config, dao)
    
    # 模拟下单模块
    import sys
    sys.modules['trade.place_order'] = MockPlaceOrderModule()
    
    try:
        # 测试下单参数
        order_params = {
            'instrument_id': 'BTC-USDT-SWAP',
            'order_type': 'market',
            'side': 'buy',
            'price': 1029432,
            'size': 0.02
        }
        
        print("1. 测试下单执行...")
        order_result = await trade_executor.execute_order(order_params)
        print(f"   下单结果: {order_result}")
        
        print("✅ 下单执行测试完成")
        
    except Exception as e:
        print(f"❌ 下单执行测试失败: {str(e)}")


if __name__ == "__main__":
    asyncio.run(test_trade_executor())
    asyncio.run(test_order_execution()) 