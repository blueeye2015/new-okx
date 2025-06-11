import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, Tuple, Optional, List, Any
import asyncio
from sqlalchemy import text
from database.dao import TradeStrategyDAO
from exchange.base import ExchangeBase
from config.settings import Config
from database.manager import DatabaseManager
from strategies.pattern_strategy import PatternStrategy

class BitcoinTradingSystem:
    def __init__(self, config: Config):
        """
        初始化交易系统
        :param config: 配置对象
        """
        self.position = None
        #self.capital = config.INITIAL_CAPITAL
        self.config = config
        self.db_manager = DatabaseManager(config.DB_CONFIG)
        self.dao = TradeStrategyDAO(self.db_manager)
        self._initialized_symbols = set()
        self._initialized_swap = set()
        
        # 设置日志
        self.setup_logging()
                
        # 模型数据缓存
        self.pattern_stats = {}
        self.volatility_data = {}
        
        # 初始化策略
        self.strategy = PatternStrategy(self)
        
        # 初始化交易所API
        self.exchange_base = ExchangeBase()
        

        # 获取实际账户余额作为初始资金
        try:
            self.capital = self.exchange_base.get_balance()
            self.logger.info(f"从账户获取初始资金: {self.capital} USDT")
        except Exception as e:
            # 如果获取失败，使用配置文件中的默认值
            #self.capital = config.DEFAULT_CAPITAL
            self.logger.warning(f"获取账户余额失败，使用默认值: {self.capital} USDT, 错误: {str(e)}")
        
        # 加载模型数据
        asyncio.create_task(self.load_model_data())

    def setup_logging(self):
        """设置日志系统"""
        logging.basicConfig(
            filename=f'trading_log_{datetime.now().strftime("%Y%m%d")}.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('BitcoinTrader')

    async def initialize_database(self):
        """初始化数据库表和函数"""
        if self.db_manager:
            await self.dao.create_table()
            self.logger.info("数据库初始化成功")

    async def load_model_data(self) -> None:
        """从数据库加载模型数据"""
        if not self.db_manager:
            return
            
        try:
            # 从price_patterns表获取数据
            pattern_data = await self.dao.get_pattern_stats_from_table()
            
            # 如果没有最近的数据，则使用默认值
            if not pattern_data:
                self._set_default_model_data()
                self.logger.warning("数据库中没有找到模型数据，使用默认值")
                return
            
            # 处理查询结果，构建pattern_stats和volatility_data字典
            self.pattern_stats = {}
            self.volatility_data = {}
            
            for row in pattern_data:
                day = row['week_period']
                pattern = row['pattern']
                win_rate = float(row['next_day_win_rate']) / 100  # 转换为小数
                return_rate = float(row['avg_next_return']) / 100  # 转换为小数
                movement = float(row['avg_movement']) / 100  # 转换为小数
                
                # 初始化当天的字典（如果不存在）
                if day not in self.pattern_stats:
                    self.pattern_stats[day] = {}
                
                # 添加模式数据
                self.pattern_stats[day][pattern] = {
                    'win_rate': win_rate,
                    'return_rate': return_rate,
                    'cases': int(row['cases'])
                }
                
                # 更新波动率数据
                self.volatility_data[day] = max(movement, self.volatility_data.get(day, 0))
            
            self.logger.info("成功从数据库加载模型数据")
                
        except Exception as e:
            self.logger.error(f"加载模型数据错误: {str(e)}")
            self._set_default_model_data()

    def _set_default_model_data(self) -> None:
        """设置默认的模型数据"""
        self.pattern_stats = {
            'Sunday': {
                'rise_then_fall': {'win_rate': 0.6125, 'return_rate': 0.0064, 'cases': 100},
                'continuous_fall': {'win_rate': 0.6036, 'return_rate': 0.0097, 'cases': 100},
                'fall_then_rise': {'win_rate': 0.4338, 'return_rate': -0.0050, 'cases': 100}
            },
            'Friday': {
                'continuous_rise': {'win_rate': 0.5669, 'return_rate': 0.0083, 'cases': 100},
                'rise_then_fall': {'win_rate': 0.5868, 'return_rate': 0.0030, 'cases': 100}
            },
            'Saturday': {
                'continuous_rise': {'win_rate': 0.4424, 'return_rate': -0.0060, 'cases': 100}
            }
        }
        self.volatility_data = {
            'Monday': 0.0299,
            'Wednesday': 0.0295,
            'Saturday': 0.0152
        }
        self.logger.warning("使用默认模型数据")

    async def execute_trade(self, price: float, day: str, price_history: pd.Series) -> Dict:
        """
        执行交易
        :param price: 当前价格
        :param day: 星期几
        :param price_history: 价格历史
        :return: 交易信息
        """
        should_trade, direction, position_size = self.strategy.should_trade(price_history, day)
        
        if not should_trade:
            return {
                'action': 'no_trade',
                'reason': 'unfavorable_conditions'
            }
            
        # 计算交易金额
        
        
        balance = self.exchange_base.get_balance()
        trade_amount = balance * position_size
        
        # 设置止损和止盈
        stop_loss = self.strategy.set_stop_loss(price, day)
        take_profit = price * (1 + (price - stop_loss) / price * 1.5)  # 1.5倍风险收益比
        
        # 创建持仓记录
        self.position = {
            'direction': direction,
            'entry_price': price,
            'size': trade_amount,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': datetime.now(),
            'pattern': self.strategy.analyze_pattern(price_history),
            'day': day
        }
        
        # 执行实际下单
        try:
            from trade.place_order import OkexOrderManager
            order_manager = OkexOrderManager(is_simulated=self.config.IS_SIMULATED)
            
            # 计算下单数量 (BTC数量)
            btc_amount = trade_amount / price
            
            # 执行下单
            order_result = order_manager.place_order(
                instrument_id=self.config.TRADING_SYMBOL,
                order_type="market",
                side="buy" if direction == "long" else "sell",
                price=price,
                size=btc_amount
            )
            
            self.logger.info(f"Opening trade: {self.position}")
            self.logger.info(f"Order result: {order_result}")
            
            return {
                'action': 'open_trade',
                'details': self.position,
                'order_result': order_result
            }
            
        except Exception as e:
            self.logger.error(f"下单失败: {str(e)}")
            self.position = None
            return {
                'action': 'trade_failed',
                'reason': str(e)
            }

    async def update_trade(self, current_price: float) -> Dict:
        """
        更新交易状态
        :param current_price: 当前价格
        :return: 更新信息
        """
        if not self.position:
            return {'action': 'no_position'}
        
        # 先检查是否需要平仓
        exit_signal = self.strategy.check_exit_signals(self.position, current_price)
        if exit_signal['action'] == 'close_position':
            return await self.close_position(current_price, exit_signal['reason'])
        
        # 如果不需要平仓，更新持仓状态
        update_result = self.strategy.update_position(self.position, current_price)
        self.position = update_result['position']  # 更新持仓信息
        
        return update_result

    async def close_position(self, price: float, reason: str) -> Dict:
        """
        平仓
        :param price: 当前价格
        :param reason: 平仓原因
        :return: 平仓信息
        """
        if not self.position:
            return {'action': 'no_position'}
            
        profit = (price - self.position['entry_price']) * \
                (1 if self.position['direction'] == 'long' else -1)
        profit_pct = profit / self.position['entry_price']
        
        trade_result = {
            'entry_time': self.position['entry_time'],
            'exit_time': datetime.now(),
            'entry_price': self.position['entry_price'],
            'exit_price': price,
            'profit_pct': profit_pct,
            'profit_amount': profit * self.position['size'],
            'day_of_week': self.position['day'],
            'pattern_type': self.position['pattern'],
            'exit_reason': reason
        }
        
        # 执行实际平仓操作
        try:
            from trade.place_order import OkexOrderManager
            order_manager = OkexOrderManager(is_simulated=self.config.IS_SIMULATED)
            
            # 计算平仓数量
            btc_amount = self.position['size'] / self.position['entry_price']
            
            # 执行平仓
            order_result = order_manager.place_order(
                instrument_id=self.config.TRADING_SYMBOL,
                order_type="market",
                side="sell" if self.position['direction'] == "long" else "buy",
                price=price,
                size=btc_amount
            )
            
            self.logger.info(f"Closing trade: {trade_result}")
            self.logger.info(f"Close order result: {order_result}")
            
            # 更新资金
            self.capital += trade_result['profit_amount']
            
            # 记录交易结果到数据库
            if self.db_manager:
                await self.record_trade(trade_result)
            
            self.position = None
            
            return {
                'action': 'close_position',
                'details': trade_result,
                'order_result': order_result
            }
            
        except Exception as e:
            self.logger.error(f"平仓失败: {str(e)}")
            return {
                'action': 'close_failed',
                'reason': str(e)
            }
        
    async def record_trade(self, trade_result: Dict) -> None:
        """
        记录交易结果到数据库
        :param trade_result: 交易结果
        """
        if not self.db_manager:
            return
            
        try:
            await self.dao.record_trade(trade_result)
            
            # 如果交易记录超过一定数量，更新模型数据
            should_update = await self.dao.should_update_model()
            if should_update:
                await self.refresh_model_data()
                
        except Exception as e:
            self.logger.error(f"记录交易错误: {str(e)}")

    async def refresh_model_data(self) -> None:
        """刷新模型数据"""
        async with self.db_manager.get_session() as session:
            try:
                # 首先检查是否存在get_price_patterns函数
                # 如果存在，需要确保该函数返回的结构与新表结构匹配
                check_function = await session.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc WHERE proname = 'get_price_patterns'
                );
                """))
                function_exists = check_function.scalar()
                
                if function_exists:
                    # 如果函数存在，使用函数刷新数据
                    await session.execute(text("""
                    INSERT INTO price_patterns (
                        week_period, pattern, cases, avg_next_return, 
                        next_day_win_rate, avg_current_return, avg_movement, updated_at
                    )
                    SELECT 
                        week_period, 
                        pattern,
                        cases,
                        avg_next_return,
                        next_day_win_rate,
                        avg_current_return,
                        avg_movement,
                        NOW()
                    FROM 
                        get_price_patterns()
                    ON CONFLICT (week_period, pattern) 
                    DO UPDATE SET
                        cases = EXCLUDED.cases,
                        avg_next_return = EXCLUDED.avg_next_return,
                        next_day_win_rate = EXCLUDED.next_day_win_rate,
                        avg_current_return = EXCLUDED.avg_current_return,
                        avg_movement = EXCLUDED.avg_movement,
                        updated_at = NOW();
                    """))
                else:
                    # 如果函数不存在，则从交易历史计算统计数据
                    # 这里是一个替代方案，根据实际情况可能需要调整
                    await session.execute(text("""
                    INSERT INTO price_patterns (
                        week_period, pattern, cases, avg_next_return, 
                        next_day_win_rate, avg_current_return, avg_movement, updated_at
                    )
                    SELECT 
                        day_of_week as week_period,
                        pattern_type as pattern,
                        COUNT(*) as cases,
                        AVG(profit_pct) * 100 as avg_next_return,
                        SUM(CASE WHEN profit_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as next_day_win_rate,
                        AVG(ABS(exit_price - entry_price) / entry_price) * 100 as avg_current_return,
                        AVG(ABS(exit_price - entry_price) / entry_price) * 100 as avg_movement,
                        NOW()
                    FROM 
                        trade_history
                    WHERE 
                        exit_time > NOW() - INTERVAL '90 days'
                    GROUP BY 
                        day_of_week, pattern_type
                    ON CONFLICT (week_period, pattern) 
                    DO UPDATE SET
                        cases = EXCLUDED.cases,
                        avg_next_return = EXCLUDED.avg_next_return,
                        next_day_win_rate = EXCLUDED.next_day_win_rate,
                        avg_current_return = EXCLUDED.avg_current_return,
                        avg_movement = EXCLUDED.avg_movement,
                        updated_at = NOW();
                    """))
                
                await session.commit()
                logging.info("模型数据已刷新")
                
                # 刷新后重新加载模型数据
                await self.load_model_data()
                
            except Exception as e:
                await session.rollback()
                logging.error(f"刷新模型数据时出错: {e}")
                raise e

    async def get_current_price(self) -> float:
        """
        获取当前价格
        :return: 当前价格
        """
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # 使用OKX API获取当前价格
                ticker_data = self.exchange_base.get_ticker(self.config.TRADING_SYMBOL)
                
                if ticker_data and 'data' in ticker_data and ticker_data['data']:
                    # OKX API返回的价格在data[0]中的last字段
                    last_price = float(ticker_data['data'][0].get('last'))
                    if last_price is not None:
                        return last_price
                    else:
                        raise ValueError(f"No last price in ticker data: {ticker_data}")
                else:
                    raise ValueError(f"Invalid ticker data received: {ticker_data}")
                    
            except Exception as e:
                self.logger.error(f"获取当前价格错误 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避
                else:
                    raise Exception(f"获取价格失败，已重试 {max_retries} 次: {str(e)}")

    async def get_price_history(self, hours: int = 4) -> pd.Series:
        """
        获取价格历史
        :param hours: 获取多少小时的数据
        :return: 价格历史Series
        """
        try:
            # 使用OKX API获取K线数据
            kline_data = self.exchange_base.get_candlesticks(
                symbol=self.config.TRADING_SYMBOL,
                bar='1H',  # 1小时K线
                limit=hours
            )
            
            if not kline_data or 'data' not in kline_data:
                raise ValueError(f"Invalid kline data received: {kline_data}")
            
            # OKX API返回的数据格式转换为DataFrame
            # data字段包含一个列表，每个元素是[ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
            columns = ['ts', 'o', 'h', 'l', 'c', 'vol', 'volCcy', 'volCcyQuote', 'confirm']
            df = pd.DataFrame(kline_data['data'], columns=columns)
            
            # 转换时间戳和数据类型
            df['ts'] = pd.to_datetime(df['ts'].astype(float), unit='ms')
            df['c'] = df['c'].astype(float)  # 收盘价转为float
            df.set_index('ts', inplace=True)
            
            # 按时间升序排序
            df.sort_index(inplace=True)
            
            # 返回收盘价Series
            return df['c']
            
        except Exception as e:
            self.logger.error(f"获取价格历史错误: {str(e)}")
            raise e

    async def run_trading_loop(self) -> None:
        """
        运行交易循环
        """
        while True:
            try:
                # 获取当前价格和价格历史
                current_price = await self.get_current_price()
                price_history = await self.get_price_history(hours=4)
                
                # 获取当前星期几
                day_of_week = datetime.now().strftime('%A')
                
                # 如果没有持仓，检查是否应该开仓
                if not self.position:
                    await self.execute_trade(current_price, day_of_week, price_history)
                else:
                    # 如果有持仓，更新持仓状态
                    await self.update_trade(current_price)
                
                # 每10秒检查一次
                await asyncio.sleep(10)
                
            except Exception as e:
                self.logger.error(f"交易循环错误: {str(e)}")
                await asyncio.sleep(60)  # 出错后等待1分钟再继续

    async def run_scheduled_tasks(self) -> None:
        """运行定时任务"""
        while True:
            await asyncio.gather(
                self.refresh_model_data()
            )
            # 每8小时更新一次模型数据
            await asyncio.sleep(8 * 60 * 60)

    async def run(self) -> None:
        """
        启动系统
        """
        # 初始化数据库
        await self.initialize_database()
        
        # 启动交易循环和定时任务
        await asyncio.gather(
            self.run_trading_loop(),
            self.run_scheduled_tasks()
        )
