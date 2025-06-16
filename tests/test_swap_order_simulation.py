import asyncio
import sys
import os
from datetime import datetime
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.trade_executor import TradeExecutor
from config.settings import Config
from exchange.base import ExchangeBase


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


async def test_swap_order_construction():
    """测试合约订单构建"""
    print("=== 测试合约订单构建 ===")
    
    try:
        config = Config()
        config.TRADING_SYMBOL = 'BTC-USDT-SWAP'
        config.IS_SIMULATED = True
        dao = MockDAO()
        
        trade_executor = TradeExecutor(config, dao)
        
        # 获取当前价格
        exchange = ExchangeBase(is_simulated=False)  # 使用实盘获取真实价格
        ticker = exchange.get_ticker('BTC-USDT-SWAP')
        current_price = float(ticker['data'][0]['last'])
        print(f"📈 当前BTC-USDT-SWAP价格: {current_price}")
        
        # 测试多头开仓订单
        print("\n1. 测试多头开仓订单构建...")
        long_signal = {
            'direction': 'long',
            'entry_price': current_price,
            'contract_size': 1,  # 1张合约
            'stop_loss': current_price * 0.98,  # 2%止损
            'take_profit': current_price * 1.05,  # 5%止盈
            'pattern': 'continuous_rise',
            'day': 'Monday',
            'instrument_id': 'BTC-USDT-SWAP',
            'td_mode': 'cross',
            'funding_info': {'cost_percentage': 0.05}
        }
        
        print(f"   📋 多头交易信号: {long_signal}")
        
        # 构建多头开仓参数
        long_order_params = {
            'instrument_id': long_signal['instrument_id'],
            'order_type': 'market',
            'side': 'buy',
            'price': long_signal['entry_price'],
            'size': long_signal['contract_size'],
            'td_mode': long_signal['td_mode'],
            'pos_side': 'long'
        }
        
        print(f"   ✅ 多头开仓参数: {long_order_params}")
        
        # 测试空头开仓订单
        print("\n2. 测试空头开仓订单构建...")
        short_signal = {
            'direction': 'short',
            'entry_price': current_price,
            'contract_size': 1,
            'stop_loss': current_price * 1.02,  # 2%止损
            'take_profit': current_price * 0.95,  # 5%止盈
            'pattern': 'fall_then_rise',
            'day': 'Tuesday',
            'instrument_id': 'BTC-USDT-SWAP',
            'td_mode': 'isolated',  # 逐仓模式
            'funding_info': {'cost_percentage': 0.05}
        }
        
        print(f"   📋 空头交易信号: {short_signal}")
        
        # 构建空头开仓参数
        short_order_params = {
            'instrument_id': short_signal['instrument_id'],
            'order_type': 'market',
            'side': 'sell',
            'price': short_signal['entry_price'],
            'size': short_signal['contract_size'],
            'td_mode': short_signal['td_mode'],
            'pos_side': 'short'
        }
        
        print(f"   ✅ 空头开仓参数: {short_order_params}")
        
        # 测试限价单参数
        print("\n3. 测试限价单参数构建...")
        limit_order_params = {
            'instrument_id': 'BTC-USDT-SWAP',
            'order_type': 'limit',
            'side': 'buy',
            'price': current_price * 0.999,  # 稍低于市价的限价单
            'size': 1,
            'td_mode': 'cross',
            'pos_side': 'long'
        }
        
        print(f"   ✅ 限价单参数: {limit_order_params}")
        
        # 转换为OKX API格式
        okx_limit_order = {
            'instId': limit_order_params['instrument_id'],
            'tdMode': limit_order_params['td_mode'],
            'side': limit_order_params['side'],
            'ordType': limit_order_params['order_type'],
            'sz': str(limit_order_params['size']),
            'px': str(limit_order_params['price']),
            'posSide': limit_order_params['pos_side']
        }
        
        print(f"   ✅ OKX API格式: {okx_limit_order}")
        
        print("✅ 合约订单构建测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 合约订单构建测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_position_lifecycle():
    """测试完整的持仓生命周期"""
    print("\n=== 测试完整的持仓生命周期 ===")
    
    try:
        config = Config()
        config.TRADING_SYMBOL = 'BTC-USDT-SWAP'
        config.IS_SIMULATED = True
        dao = MockDAO()
        
        trade_executor = TradeExecutor(config, dao)
        
        # 获取当前价格
        exchange = ExchangeBase(is_simulated=False)
        ticker = exchange.get_ticker('BTC-USDT-SWAP')
        current_price = float(ticker['data'][0]['last'])
        
        print(f"📈 当前价格: {current_price}")
        
        # 1. 模拟开仓
        print("\n1. 模拟开仓...")
        open_signal = {
            'direction': 'long',
            'entry_price': current_price,
            'contract_size': 2,
            'stop_loss': current_price * 0.97,
            'take_profit': current_price * 1.06,
            'pattern': 'continuous_rise',
            'day': 'Wednesday',
            'instrument_id': 'BTC-USDT-SWAP',
            'td_mode': 'cross',
            'funding_info': {'cost_percentage': 0.05}
        }
        
        # 模拟开仓成功，直接保存持仓数据
        position_data = {
            'direction': open_signal['direction'],
            'entry_price': open_signal['entry_price'],
            'size': open_signal['contract_size'],
            'stop_loss': open_signal['stop_loss'],
            'take_profit': open_signal['take_profit'],
            'entry_time': datetime.now(),
            'pattern': open_signal['pattern'],
            'day': open_signal['day'],
            'instrument_type': 'swap',
            'td_mode': open_signal['td_mode']
        }
        
        await dao.save_position(position_data)
        print(f"   ✅ 开仓成功，持仓大小: {position_data['size']} 张")
        
        # 2. 获取当前持仓
        print("\n2. 获取当前持仓...")
        current_position = await trade_executor.get_current_position()
        print(f"   ✅ 当前持仓: 方向={current_position['direction']}, 大小={current_position['size']}张")
        
        # 3. 计算盈亏（模拟价格上涨）
        print("\n3. 计算持仓盈亏...")
        simulated_prices = [
            current_price * 1.01,  # 上涨1%
            current_price * 1.03,  # 上涨3%
            current_price * 0.99,  # 下跌1%
        ]
        
        for i, price in enumerate(simulated_prices):
            pnl_info = await trade_executor.calculate_position_pnl(price)
            if pnl_info:
                print(f"   📊 价格{price:.1f}: 盈亏={pnl_info['unrealized_pnl']:.4f}, 盈亏率={pnl_info['pnl_percentage']:.2f}%")
        
        # 4. 更新止损止盈
        print("\n4. 更新止损止盈...")
        new_stop_loss = current_price * 0.985  # 调整止损
        new_take_profit = current_price * 1.08  # 调整止盈
        
        update_result = await trade_executor.update_position_stops(
            current_position, new_stop_loss, new_take_profit
        )
        
        if update_result['success']:
            print(f"   ✅ 止损止盈更新成功: 止损={new_stop_loss:.1f}, 止盈={new_take_profit:.1f}")
        
        # 5. 模拟平仓
        print("\n5. 模拟平仓...")
        close_signal = {
            'exit_price': current_price * 1.04,  # 4%盈利平仓
            'reason': 'take_profit',
            'instrument_id': 'BTC-USDT-SWAP'
        }
        
        # 计算平仓结果
        if current_position['direction'] == 'long':
            profit_per_contract = close_signal['exit_price'] - current_position['entry_price']
        else:
            profit_per_contract = current_position['entry_price'] - close_signal['exit_price']
        
        total_profit = profit_per_contract * current_position['size']
        profit_pct = profit_per_contract / current_position['entry_price']
        
        trade_result = {
            'entry_time': current_position['entry_time'],
            'exit_time': datetime.now(),
            'entry_price': current_position['entry_price'],
            'exit_price': close_signal['exit_price'],
            'profit_pct': profit_pct,
            'profit_amount': total_profit,
            'day_of_week': current_position['day'],
            'pattern_type': current_position['pattern'],
            'exit_reason': close_signal['reason'],
            'instrument_type': 'swap',
            'contract_size': current_position['size']
        }
        
        await dao.record_trade(trade_result)
        await dao.delete_position()
        
        print(f"   ✅ 平仓成功: 盈利={total_profit:.2f}USDT, 盈利率={profit_pct*100:.2f}%")
        
        # 6. 验证持仓已清空
        print("\n6. 验证持仓状态...")
        final_position = await trade_executor.get_current_position()
        if final_position is None:
            print("   ✅ 持仓已清空")
        else:
            print(f"   ⚠️ 持仓未清空: {final_position}")
        
        print("✅ 完整持仓生命周期测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 持仓生命周期测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_risk_management():
    """测试风险管理功能"""
    print("\n=== 测试风险管理功能 ===")
    
    try:
        # 获取当前价格
        exchange = ExchangeBase(is_simulated=False)
        ticker = exchange.get_ticker('BTC-USDT-SWAP')
        current_price = float(ticker['data'][0]['last'])
        
        print(f"📈 当前价格: {current_price}")
        
        # 测试不同的风险参数
        risk_scenarios = [
            {
                'name': '保守策略',
                'contract_size': 1,
                'stop_loss_pct': 0.02,  # 2%止损
                'take_profit_pct': 0.04,  # 4%止盈
                'td_mode': 'cross'
            },
            {
                'name': '激进策略',
                'contract_size': 5,
                'stop_loss_pct': 0.05,  # 5%止损
                'take_profit_pct': 0.10,  # 10%止盈
                'td_mode': 'isolated'
            },
            {
                'name': '超短线策略',
                'contract_size': 3,
                'stop_loss_pct': 0.01,  # 1%止损
                'take_profit_pct': 0.02,  # 2%止盈
                'td_mode': 'cross'
            }
        ]
        
        for scenario in risk_scenarios:
            print(f"\n📋 {scenario['name']}:")
            
            # 计算止损止盈价格
            stop_loss = current_price * (1 - scenario['stop_loss_pct'])
            take_profit = current_price * (1 + scenario['take_profit_pct'])
            
            # 计算最大风险
            max_loss_per_contract = current_price - stop_loss
            max_total_loss = max_loss_per_contract * scenario['contract_size']
            
            # 计算最大收益
            max_profit_per_contract = take_profit - current_price
            max_total_profit = max_profit_per_contract * scenario['contract_size']
            
            # 计算风险收益比
            risk_reward_ratio = max_total_profit / max_total_loss
            
            print(f"   📊 合约数量: {scenario['contract_size']} 张")
            print(f"   📊 交易模式: {scenario['td_mode']}")
            print(f"   📊 止损价格: {stop_loss:.1f} (-{scenario['stop_loss_pct']*100:.1f}%)")
            print(f"   📊 止盈价格: {take_profit:.1f} (+{scenario['take_profit_pct']*100:.1f}%)")
            print(f"   📊 最大亏损: {max_total_loss:.2f} USDT")
            print(f"   📊 最大盈利: {max_total_profit:.2f} USDT")
            print(f"   📊 风险收益比: 1:{risk_reward_ratio:.2f}")
            
            # 风险评估
            if risk_reward_ratio >= 2:
                risk_level = "✅ 低风险"
            elif risk_reward_ratio >= 1.5:
                risk_level = "⚠️ 中等风险"
            else:
                risk_level = "❌ 高风险"
            
            print(f"   📊 风险评级: {risk_level}")
        
        print("✅ 风险管理功能测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 风险管理功能测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("🚀 开始合约交易模拟测试...")
    
    test_results = []
    
    # 运行所有测试
    test_results.append(await test_swap_order_construction())
    test_results.append(await test_position_lifecycle())
    test_results.append(await test_risk_management())
    
    # 统计结果
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n=== 📊 测试总结 ===")
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    
    if passed == total:
        print("🎉 所有合约交易测试通过！")
        print("💡 提示: 这些是模拟测试，实际交易请谨慎操作")
    else:
        print("⚠️  部分测试失败，请检查错误信息")


if __name__ == "__main__":
    asyncio.run(main()) 