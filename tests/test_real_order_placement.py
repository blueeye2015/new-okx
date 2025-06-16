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


async def test_real_limit_order():
    """测试实际限价单下单（不会成交）"""
    print("🚀 开始实际限价单下单测试...")
    print("⚠️  注意：这将在OKX实际下单，但价格设置得很低不会成交")
    
    # 确认用户同意
    confirm = input("确认要进行实际下单测试吗？(输入 'yes' 确认): ")
    if confirm.lower() != 'yes':
        print("❌ 用户取消测试")
        return False
    
    try:
        # 获取当前价格
        exchange = ExchangeBase(is_simulated=False)  # 使用实盘
        ticker = exchange.get_ticker('BTC-USDT-SWAP')
        current_price = float(ticker['data'][0]['last'])
        
        print(f"📈 当前BTC-USDT-SWAP价格: {current_price}")
        
        # 设置一个很低的限价单价格（比当前价格低5%，确保不会成交）
        limit_price = current_price * 0.95
        print(f"📋 限价单价格: {limit_price} (比市价低5%)")
        
        # 创建交易执行器
        config = Config()
        config.TRADING_SYMBOL = 'BTC-USDT-SWAP'
        config.IS_SIMULATED = False  # 使用实盘
        dao = MockDAO()
        
        trade_executor = TradeExecutor(config, dao)
        
        # 构建限价单参数
        order_params = {
            'instrument_id': 'BTC-USDT-SWAP',
            'order_type': 'limit',  # 限价单
            'side': 'buy',  # 买入
            'price': limit_price,
            'size': 1,  # 1张合约（最小单位）
            'td_mode': 'cross',  # 全仓模式
            'pos_side': 'net'  # 净持仓模式（默认）
        }
        
        print(f"📋 订单参数: {order_params}")
        
        # 执行下单
        print("\n🔄 正在下单...")
        order_result = await trade_executor.execute_swap_order(order_params)
        
        if order_result['success']:
            order_api_result = order_result['order_result']
            
            # 检查API返回结果
            if order_api_result.get('code') == '0':
                print("✅ 下单成功！")
                print(f"📊 订单结果: {order_api_result}")
                
                # 提取订单ID
                if 'data' in order_api_result and order_api_result['data']:
                    order_data = order_api_result['data'][0]
                    order_id = order_data.get('ordId', 'Unknown')
                    print(f"📝 订单ID: {order_id}")
                    print(f"📱 请在OKX APP中查看订单状态")
                    print(f"💡 订单详情: 买入1张BTC-USDT-SWAP，限价{limit_price}")
                    
                    # 等待用户确认
                    print("\n⏳ 请在OKX APP中确认看到订单后按任意键继续...")
                    try:
                        input()
                    except EOFError:
                        print("自动继续...")
                    
                    # 询问是否取消订单
                    try:
                        cancel_confirm = input("是否取消这个订单？(输入 'yes' 取消，其他键跳过): ")
                        if cancel_confirm.lower() == 'yes':
                            await cancel_order(order_id)
                        else:
                            print("⚠️  订单未取消，请手动在APP中取消")
                    except EOFError:
                        print("自动跳过取消操作")
                else:
                    print("⚠️  无法获取订单ID")
            else:
                print("❌ 下单失败！")
                print(f"错误代码: {order_api_result.get('code')}")
                print(f"错误信息: {order_api_result.get('msg')}")
                if 'data' in order_api_result and order_api_result['data']:
                    for error in order_api_result['data']:
                        print(f"详细错误: {error.get('sCode')} - {error.get('sMsg')}")
                return False
            
            return True
        else:
            print("❌ 下单失败！")
            print(f"错误信息: {order_result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def cancel_order(order_id: str):
    """取消订单"""
    try:
        print(f"\n🔄 正在取消订单 {order_id}...")
        
        from okex.Trade_api import TradeAPI
        from exchange.base import ExchangeBase
        
        # 获取API凭证
        exchange = ExchangeBase(is_simulated=False)
        
        trade_api = TradeAPI(
            exchange.api_key,
            exchange.secret_key,
            exchange.passphrase,
            False,  # use_server_time
            exchange.flag,
            proxies=exchange.proxies
        )
        
        # 取消订单
        cancel_result = trade_api.cancel_order(
            instId='BTC-USDT-SWAP',
            ordId=order_id
        )
        
        print(f"📊 取消结果: {cancel_result}")
        
        if cancel_result.get('code') == '0':
            print("✅ 订单取消成功！")
        else:
            print(f"❌ 订单取消失败: {cancel_result}")
            
    except Exception as e:
        print(f"❌ 取消订单失败: {str(e)}")


async def test_order_query():
    """测试查询订单状态"""
    print("\n=== 测试查询订单状态 ===")
    
    try:
        from okex.Trade_api import TradeAPI
        from exchange.base import ExchangeBase
        
        exchange = ExchangeBase(is_simulated=False)
        
        trade_api = TradeAPI(
            exchange.api_key,
            exchange.secret_key,
            exchange.passphrase,
            False,
            exchange.flag,
            proxies=exchange.proxies
        )
        
        # 查询未成交订单
        pending_orders = trade_api.get_order_list(
            instType='SWAP',
            instId='BTC-USDT-SWAP',
            state='live'  # 未成交订单
        )
        
        print(f"📊 未成交订单: {pending_orders}")
        
        if pending_orders.get('code') == '0' and pending_orders.get('data'):
            orders = pending_orders['data']
            print(f"📝 找到 {len(orders)} 个未成交订单")
            
            for i, order in enumerate(orders):
                print(f"   订单 {i+1}:")
                print(f"     ID: {order.get('ordId')}")
                print(f"     价格: {order.get('px')}")
                print(f"     数量: {order.get('sz')}")
                print(f"     状态: {order.get('state')}")
                print(f"     时间: {order.get('cTime')}")
        else:
            print("📝 没有找到未成交订单")
            
        return True
        
    except Exception as e:
        print(f"❌ 查询订单失败: {str(e)}")
        return False


async def test_account_info():
    """测试获取账户信息"""
    print("\n=== 测试获取账户信息 ===")
    
    try:
        exchange = ExchangeBase(is_simulated=False)
        
        # 获取账户余额
        balance = exchange.get_balance('USDT')
        print(f"💰 USDT余额: {balance}")
        
        # 获取持仓信息
        positions = exchange.get_positions('SWAP')
        print(f"📊 合约持仓: {positions}")
        
        return True
        
    except Exception as e:
        print(f"❌ 获取账户信息失败: {str(e)}")
        return False


async def main():
    """主测试函数"""
    print("🎯 OKX实际下单测试")
    print("=" * 50)
    
    # 先测试账户信息
    print("1. 测试账户连接...")
    account_ok = await test_account_info()
    
    if not account_ok:
        print("❌ 账户连接失败，无法继续测试")
        return
    
    # 查询现有订单
    print("\n2. 查询现有订单...")
    await test_order_query()
    
    # 实际下单测试
    print("\n3. 实际下单测试...")
    order_ok = await test_real_limit_order()
    
    # 再次查询订单状态
    if order_ok:
        print("\n4. 查询订单状态...")
        await test_order_query()
    
    print("\n" + "=" * 50)
    print("🎉 测试完成！")
    print("💡 提示：请在OKX APP中确认订单状态")


if __name__ == "__main__":
    asyncio.run(main()) 