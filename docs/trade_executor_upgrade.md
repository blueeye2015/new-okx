# TradeExecutor 合约交易功能升级

## 概述

本次升级为 `TradeExecutor` 类添加了完整的合约交易功能，支持现货和合约交易的统一管理。升级后的系统可以：

- 自动识别现货和合约交易对
- 支持OKX合约API的完整功能
- 提供完整的持仓生命周期管理
- 集成风险管理功能

## 新增功能

### 1. 合约下单功能

#### `execute_swap_order(order_params: Dict) -> Dict`
- **功能**: 执行合约下单操作
- **支持**: 市价单、限价单
- **交易模式**: 全仓(cross)、逐仓(isolated)
- **持仓方向**: 净持仓(net)、多头(long)、空头(short)

```python
# 合约下单示例
order_params = {
    'instrument_id': 'BTC-USDT-SWAP',
    'order_type': 'market',  # 或 'limit'
    'side': 'buy',  # 或 'sell'
    'price': 50000,
    'size': 1,  # 合约张数
    'td_mode': 'cross',  # 或 'isolated'
    'pos_side': 'long'  # 或 'short', 'net'
}

result = await trade_executor.execute_swap_order(order_params)
```

### 2. 合约持仓管理

#### `open_swap_position(trade_signal: Dict) -> Dict`
- **功能**: 开合约仓位
- **特点**: 自动构建订单参数，保存持仓信息

#### `close_swap_position(close_signal: Dict) -> Dict`
- **功能**: 平合约仓位
- **特点**: 自动计算盈亏，记录交易结果

#### `get_swap_positions() -> Dict`
- **功能**: 获取当前合约持仓
- **数据源**: 直接从OKX API获取

```python
# 合约开仓示例
trade_signal = {
    'direction': 'long',
    'entry_price': 50000,
    'contract_size': 1,
    'stop_loss': 49000,
    'take_profit': 52000,
    'pattern': 'continuous_rise',
    'day': 'Monday',
    'instrument_id': 'BTC-USDT-SWAP',
    'td_mode': 'cross'
}

result = await trade_executor.open_swap_position(trade_signal)
```

### 3. 智能订单路由

#### `execute_order(order_params: Dict) -> Dict`
- **功能**: 自动判断现货或合约交易
- **判断逻辑**: 根据 `instrument_id` 中是否包含 'SWAP' 或 'FUTURES'
- **路由**: 自动调用对应的现货或合约下单方法

### 4. 增强的持仓管理

所有持仓数据现在包含 `instrument_type` 字段：
- `'spot'`: 现货持仓
- `'swap'`: 合约持仓

支持的交易模式：
- `'cross'`: 全仓模式
- `'isolated'`: 逐仓模式

## API集成

### OKX Trade API 集成

使用 `okex.Trade_api.TradeAPI` 进行合约交易：

```python
from okex.Trade_api import TradeAPI

trade_api = TradeAPI(
    api_key, secret_key, passphrase,
    False,  # use_server_time
    flag,   # '0' 实盘, '1' 模拟盘
    proxies=proxies
)

# 下单参数格式
order_data = {
    'instId': 'BTC-USDT-SWAP',
    'tdMode': 'cross',
    'side': 'buy',
    'ordType': 'market',
    'sz': '1',
    'posSide': 'long'
}

result = trade_api.place_order(**order_data)
```

## 测试覆盖

### 1. 基础连接测试 (`test_trade_executor_real.py`)
- ✅ API环境自动检测
- ✅ 实盘/模拟盘自适应
- ✅ 交易所基础功能测试
- ✅ 现货和合约功能测试
- ✅ 订单参数验证
- ✅ 持仓管理功能

### 2. 合约交易模拟测试 (`test_swap_order_simulation.py`)
- ✅ 合约订单构建测试
- ✅ 完整持仓生命周期测试
- ✅ 风险管理功能测试
- ✅ 多种交易策略模拟

## 风险管理功能

### 风险参数计算
- **止损止盈**: 自动计算基于百分比的止损止盈价格
- **风险收益比**: 自动计算每笔交易的风险收益比
- **风险评级**: 基于风险收益比的自动评级

### 支持的策略类型
1. **保守策略**: 小仓位，低风险，稳定收益
2. **激进策略**: 大仓位，高风险，高收益
3. **超短线策略**: 中等仓位，极小止损，快进快出

## 使用示例

### 完整的合约交易流程

```python
import asyncio
from trading.trade_executor import TradeExecutor
from config.settings import Config
from database.dao import TradeStrategyDAO

async def main():
    # 初始化
    config = Config()
    config.TRADING_SYMBOL = 'BTC-USDT-SWAP'
    config.IS_SIMULATED = True
    
    dao = TradeStrategyDAO()
    trade_executor = TradeExecutor(config, dao)
    
    # 1. 开仓
    trade_signal = {
        'direction': 'long',
        'entry_price': 50000,
        'contract_size': 1,
        'stop_loss': 49000,
        'take_profit': 52000,
        'pattern': 'continuous_rise',
        'day': 'Monday',
        'td_mode': 'cross'
    }
    
    open_result = await trade_executor.open_swap_position(trade_signal)
    print(f"开仓结果: {open_result}")
    
    # 2. 监控持仓
    position = await trade_executor.get_current_position()
    pnl = await trade_executor.calculate_position_pnl(51000)
    print(f"当前盈亏: {pnl}")
    
    # 3. 平仓
    close_signal = {
        'exit_price': 51500,
        'reason': 'take_profit'
    }
    
    close_result = await trade_executor.close_swap_position(close_signal)
    print(f"平仓结果: {close_result}")

if __name__ == "__main__":
    asyncio.run(main())
```

## 配置要求

### 环境变量
确保 `.env` 文件包含正确的OKX API凭证：
```
API_KEY=your_api_key
SECRET_KEY=your_secret_key
PASSPHRASE=your_passphrase
```

### 交易对配置
- **现货**: `BTC-USDT`, `ETH-USDT` 等
- **合约**: `BTC-USDT-SWAP`, `ETH-USDT-SWAP` 等

## 注意事项

1. **模拟盘测试**: 建议先在模拟盘环境测试所有功能
2. **API权限**: 确保API密钥有合约交易权限
3. **风险控制**: 合约交易风险较高，请谨慎设置仓位大小
4. **资金管理**: 建议使用逐仓模式控制单笔交易风险

## 升级兼容性

- ✅ 完全向后兼容现有现货交易功能
- ✅ 数据库结构自动适配新字段
- ✅ 配置文件无需修改
- ✅ 现有策略无需调整

## 性能优化

- 使用单例模式的 `ExchangeBase` 减少API连接开销
- 异步操作提高并发性能
- 智能缓存减少重复API调用
- 错误重试机制提高稳定性

---

**版本**: v2.0  
**更新日期**: 2025-06-16  
**兼容性**: Python 3.7+, OKX API v5 