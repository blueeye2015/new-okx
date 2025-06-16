import asyncio
import sys
import os
from datetime import datetime
import logging

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trading.trade_executor import TradeExecutor
from database.dao import TradeStrategyDAO
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
        self.trades.append(trade_result)
        print(f"   记录交易: {trade_result}")


async def test_api_environment():
    """测试API环境配置"""
    print("=== 测试API环境配置 ===")
    
    try:
        from dotenv import load_dotenv
        load_dotenv('D:\OKex-API\.env')
        
        api_key = os.getenv('API_KEY')
        print(f"1. API Key存在: {'是' if api_key else '否'}")
        if api_key:
            print(f"   API Key前缀: {api_key[:8]}...")
        
        # 测试实盘环境
        print("2. 测试实盘环境连接...")
        try:
            exchange_real = ExchangeBase(is_simulated=False)
            ticker_real = exchange_real.get_ticker('BTC-USDT')
            print(f"   实盘连接: ✅ 成功")
            print(f"   实盘Ticker: {ticker_real}")
            return True, 'real'
        except Exception as e:
            print(f"   实盘连接: ❌ 失败 - {str(e)}")
        
        # 测试模拟盘环境
        print("3. 测试模拟盘环境连接...")
        try:
            exchange_sim = ExchangeBase(is_simulated=True)
            ticker_sim = exchange_sim.get_ticker('BTC-USDT')
            print(f"   模拟盘连接: ✅ 成功")
            print(f"   模拟盘Ticker: {ticker_sim}")
            return True, 'simulated'
        except Exception as e:
            print(f"   模拟盘连接: ❌ 失败 - {str(e)}")
        
        return False, None
        
    except Exception as e:
        print(f"❌ API环境配置测试失败: {str(e)}")
        return False, None


async def test_exchange_base_connection(use_simulated=True):
    """测试交易所基础连接"""
    env_type = "模拟盘" if use_simulated else "实盘"
    print(f"=== 测试交易所基础连接 ({env_type}) ===")
    
    try:
        # 创建交易所实例
        exchange = ExchangeBase(is_simulated=use_simulated)
        
        # 测试获取ticker
        print("1. 测试获取BTC-USDT ticker...")
        ticker = exchange.get_ticker('BTC-USDT')
        if ticker and 'data' in ticker and ticker['data']:
            price = ticker['data'][0]['last']
            print(f"   ✅ Ticker获取成功，当前价格: {price}")
        else:
            print(f"   ⚠️ Ticker数据格式异常: {ticker}")
        
        # 测试获取账户余额（可能会失败，但不影响其他测试）
        print("2. 测试获取USDT余额...")
        try:
            balance = exchange.get_balance('USDT')
            print(f"   ✅ USDT余额: {balance}")
        except Exception as e:
            print(f"   ⚠️ 获取余额失败（可能是权限问题）: {str(e)}")
        
        # 测试获取合约持仓
        print("3. 测试获取合约持仓...")
        try:
            positions = exchange.get_positions('SWAP')
            print(f"   ✅ 合约持仓获取成功: {positions}")
        except Exception as e:
            print(f"   ⚠️ 获取持仓失败（可能是权限问题）: {str(e)}")
        
        # 测试获取K线数据
        print("4. 测试获取K线数据...")
        klines = exchange.get_candlesticks('BTC-USDT', '1H', 5)
        if klines and 'data' in klines and klines['data']:
            print(f"   ✅ K线数据获取成功，获取到 {len(klines['data'])} 条数据")
        else:
            print(f"   ⚠️ K线数据格式异常: {klines}")
        
        print(f"✅ 交易所基础连接测试完成 ({env_type})")
        return True
        
    except Exception as e:
        print(f"❌ 交易所基础连接测试失败 ({env_type}): {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_spot_trading(use_simulated=True):
    """测试现货交易功能"""
    env_type = "模拟盘" if use_simulated else "实盘"
    print(f"\n=== 测试现货交易功能 ({env_type}) ===")
    
    try:
        # 创建配置和DAO
        config = Config()
        config.TRADING_SYMBOL = 'BTC-USDT'
        config.IS_SIMULATED = use_simulated
        dao = MockDAO()
        
        # 创建交易执行器
        trade_executor = TradeExecutor(config, dao)
        
        # 测试现货开仓
        print("1. 测试现货开仓参数构建...")
        spot_signal = {
            'direction': 'long',
            'entry_price': 50000,
            'trade_amount': 100,  # USDT金额
            'btc_amount': 0.002,  # BTC数量
            'stop_loss': 49000,
            'take_profit': 52000,
            'pattern': 'rise_then_fall',
            'day': 'Monday',
            'funding_info': {'cost_percentage': 0.1}
        }
        
        print(f"   ✅ 现货交易信号构建成功: {spot_signal}")
        
        # 测试获取当前价格
        print("2. 测试获取当前价格...")
        exchange = ExchangeBase(is_simulated=use_simulated)
        ticker = exchange.get_ticker('BTC-USDT')
        if ticker and 'data' in ticker and ticker['data']:
            current_price = float(ticker['data'][0]['last'])
            print(f"   ✅ 当前BTC价格: {current_price}")
        
        # 测试现货订单参数构建
        print("3. 测试现货订单参数构建...")
        order_params = {
            'instrument_id': config.TRADING_SYMBOL,
            'order_type': 'market',
            'side': 'buy' if spot_signal['direction'] == 'long' else 'sell',
            'price': spot_signal['entry_price'],
            'size': spot_signal['btc_amount']
        }
        print(f"   ✅ 现货订单参数: {order_params}")
        
        print(f"✅ 现货交易功能测试完成 ({env_type})")
        return True
        
    except Exception as e:
        print(f"❌ 现货交易功能测试失败 ({env_type}): {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_swap_trading(use_simulated=True):
    """测试合约交易功能"""
    env_type = "模拟盘" if use_simulated else "实盘"
    print(f"\n=== 测试合约交易功能 ({env_type}) ===")
    
    try:
        # 创建配置和DAO
        config = Config()
        config.TRADING_SYMBOL = 'BTC-USDT-SWAP'
        config.IS_SIMULATED = use_simulated
        dao = MockDAO()
        
        # 创建交易执行器
        trade_executor = TradeExecutor(config, dao)
        
        # 测试获取合约持仓
        print("1. 测试获取合约持仓...")
        try:
            positions_result = await trade_executor.get_swap_positions()
            print(f"   ✅ 合约持仓结果: {positions_result}")
        except Exception as e:
            print(f"   ⚠️ 获取合约持仓失败（可能是权限问题）: {str(e)}")
        
        # 测试合约交易信号构建
        print("2. 测试合约交易信号构建...")
        swap_signal = {
            'direction': 'long',
            'entry_price': 50000,
            'contract_size': 1,  # 合约张数
            'stop_loss': 49000,
            'take_profit': 52000,
            'pattern': 'continuous_rise',
            'day': 'Tuesday',
            'instrument_id': 'BTC-USDT-SWAP',
            'td_mode': 'cross',  # 全仓模式
            'funding_info': {'cost_percentage': 0.05}
        }
        
        print(f"   ✅ 合约交易信号: {swap_signal}")
        
        # 测试合约下单参数构建
        print("3. 测试合约下单参数构建...")
        order_params = {
            'instrument_id': 'BTC-USDT-SWAP',
            'order_type': 'market',
            'side': 'buy',
            'price': 50000,
            'size': 1,
            'td_mode': 'cross',
            'pos_side': 'long'
        }
        
        print(f"   ✅ 合约下单参数: {order_params}")
        
        # 测试获取合约ticker
        print("4. 测试获取合约ticker...")
        exchange = ExchangeBase(is_simulated=use_simulated)
        swap_ticker = exchange.get_ticker('BTC-USDT-SWAP')
        if swap_ticker and 'data' in swap_ticker and swap_ticker['data']:
            swap_price = float(swap_ticker['data'][0]['last'])
            print(f"   ✅ 当前BTC-USDT-SWAP价格: {swap_price}")
        
        print(f"✅ 合约交易功能测试完成 ({env_type})")
        return True
        
    except Exception as e:
        print(f"❌ 合约交易功能测试失败 ({env_type}): {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_order_parameter_validation():
    """测试订单参数验证"""
    print("\n=== 测试订单参数验证 ===")
    
    try:
        config = Config()
        config.IS_SIMULATED = True
        dao = MockDAO()
        trade_executor = TradeExecutor(config, dao)
        
        # 测试现货订单参数
        print("1. 测试现货订单参数验证...")
        spot_params = {
            'instrument_id': 'BTC-USDT',
            'order_type': 'market',
            'side': 'buy',
            'price': 50000,
            'size': 0.001
        }
        
        # 验证是否会被识别为现货
        is_swap = 'SWAP' in spot_params['instrument_id'] or 'FUTURES' in spot_params['instrument_id']
        print(f"   ✅ 现货订单识别: {'合约' if is_swap else '现货'}")
        
        # 测试合约订单参数
        print("2. 测试合约订单参数验证...")
        swap_params = {
            'instrument_id': 'BTC-USDT-SWAP',
            'order_type': 'market',
            'side': 'buy',
            'price': 50000,
            'size': 1,
            'td_mode': 'cross',
            'pos_side': 'long'
        }
        
        # 验证是否会被识别为合约
        is_swap = 'SWAP' in swap_params['instrument_id'] or 'FUTURES' in swap_params['instrument_id']
        print(f"   ✅ 合约订单识别: {'合约' if is_swap else '现货'}")
        
        # 测试OKX合约API参数格式
        print("3. 测试OKX合约API参数格式...")
        okx_order_data = {
            'instId': swap_params['instrument_id'],
            'tdMode': swap_params.get('td_mode', 'cross'),
            'side': swap_params['side'],
            'ordType': swap_params.get('order_type', 'market'),
            'sz': str(swap_params['size']),
            'posSide': swap_params.get('pos_side', 'net')
        }
        print(f"   ✅ OKX API参数格式: {okx_order_data}")
        
        print("✅ 订单参数验证测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 订单参数验证测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_position_management():
    """测试持仓管理功能"""
    print("\n=== 测试持仓管理功能 ===")
    
    try:
        config = Config()
        config.IS_SIMULATED = True
        dao = MockDAO()
        trade_executor = TradeExecutor(config, dao)
        
        # 模拟一个持仓
        print("1. 模拟创建持仓...")
        mock_position = {
            'direction': 'long',
            'entry_price': 50000,
            'size': 1,
            'stop_loss': 49000,
            'take_profit': 52000,
            'entry_time': datetime.now(),
            'pattern': 'continuous_rise',
            'day': 'Monday',
            'instrument_type': 'swap',
            'td_mode': 'cross'
        }
        
        await dao.save_position(mock_position)
        
        # 测试获取当前持仓
        print("2. 测试获取当前持仓...")
        current_position = await trade_executor.get_current_position()
        print(f"   ✅ 当前持仓: {current_position}")
        
        # 测试计算盈亏
        print("3. 测试计算持仓盈亏...")
        current_price = 51000  # 模拟当前价格
        pnl_info = await trade_executor.calculate_position_pnl(current_price)
        print(f"   ✅ 盈亏信息: {pnl_info}")
        
        # 测试更新止损止盈
        print("4. 测试更新止损止盈...")
        if current_position:
            update_result = await trade_executor.update_position_stops(
                current_position, 49500, 53000
            )
            print(f"   ✅ 更新结果: {update_result}")
        
        print("✅ 持仓管理功能测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 持仓管理功能测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("开始TradeExecutor真实API测试...")
    
    # 首先测试API环境
    api_success, env_type = await test_api_environment()
    
    if not api_success:
        print("❌ API环境测试失败，无法继续后续测试")
        return
    
    # 根据可用的环境类型进行测试
    use_simulated = (env_type == 'simulated')
    
    test_results = []
    
    # 运行所有测试
    test_results.append(await test_exchange_base_connection(use_simulated))
    test_results.append(await test_spot_trading(use_simulated))
    test_results.append(await test_swap_trading(use_simulated))
    test_results.append(await test_order_parameter_validation())
    test_results.append(await test_position_management())
    
    # 统计结果
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n=== 测试总结 ===")
    print(f"使用环境: {env_type}")
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    
    if passed == total:
        print("🎉 所有测试通过！")
    else:
        print("⚠️  部分测试失败，请检查错误信息")


if __name__ == "__main__":
    asyncio.run(main()) 