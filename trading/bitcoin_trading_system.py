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
from trading.trade_executor import TradeExecutor
from trading.strategy_manager import StrategyManager

class BitcoinTradingSystem:
    def __init__(self, config: Config):
        """
        初始化交易系统
        :param config: 配置对象
        """
        self.config = config
        self.db_manager = DatabaseManager(config.DB_CONFIG)
        self.dao = TradeStrategyDAO(self.db_manager)
        self._initialized_symbols = set()
        self._initialized_swap = set()
        
        # 设置日志
        self.setup_logging()
        
        # 初始化交易所API
        self.exchange_base = ExchangeBase()
        
        # 获取实际账户余额作为初始资金
        try:
            self.capital = self.exchange_base.get_balance()
            self.logger.info(f"从账户获取初始资金: {self.capital} USDT")
        except Exception as e:
            self.logger.warning(f"获取账户余额失败，使用默认值: {self.capital} USDT, 错误: {str(e)}")
        
        # 初始化策略管理器和交易执行器
        self.strategy_manager = StrategyManager(config, self.dao, self.exchange_base)
        self.trade_executor = TradeExecutor(config, self.dao)
        
        # 默认合约费率
        self.default_contract_fees = {
            'perpetual': {  # 永续合约
                'maker_rate': 0.0002,      # 0.02% maker费率
                'taker_rate': 0.0005,      # 0.05% taker费率
                'funding_rate': 0.0001,    # 0.01% 资金费率（每8小时）
                'slippage_rate': 0.0005,   # 0.05% 滑点
                'insurance_rate': 0.00005, # 0.005% 保险基金费用
                'adl_rate': 0.00002,       # 0.002% ADL费用
            }}
        # 风险参数
        self.risk_params = {
            'conservative': {
                'max_leverage': 2,
                'max_position_pct': 0.2,
                'stop_loss_pct': 0.04,
                'margin_buffer': 0.2  # 保证金缓冲
            },
            'medium': {
                'max_leverage': 5,
                'max_position_pct': 0.5,
                'stop_loss_pct': 0.08,
                'margin_buffer': 0.15
            },
            'aggressive': {
                'max_leverage': 10,
                'max_position_pct': 0.8,
                'stop_loss_pct': 0.12,
                'margin_buffer': 0.1
            }
        }

    def setup_logging(self):
        """设置日志系统"""
        # 使用根日志记录器，这样所有模块的日志都会记录到同一个文件
        logging.basicConfig(
            filename='klines.log',
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('BitcoinTrader')
        self.logger.info('BitcoinTradingSystem logging initialized')

    async def initialize_database(self):
        """初始化数据库表和函数"""
        if self.db_manager:
            await self.dao.create_table()
            self.logger.info("数据库初始化成功")

    async def initialize(self):
        """
        异步初始化方法，用于加载数据并初始化策略
        """
        try:
            # 初始化策略管理器
            await self.strategy_manager.initialize_strategy()
            self.logger.info("系统初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化过程中发生错误: {str(e)}")
            raise ValueError(f"系统初始化失败: {str(e)}")

    async def execute_trade(self, price: float, day: str, price_history: pd.Series) -> Dict:
        """
        执行交易
        :param price: 当前价格
        :param day: 星期几
        :param price_history: 前一天的价格历史（2小时数据）
        :return: 交易信息
        """
        try:
            # 生成交易信号
            trade_signal = await self.strategy_manager.generate_trade_signal(price, day, price_history)
            
            if not trade_signal['should_trade']:
                return {
                    'action': 'no_trade',
                    'reason': trade_signal['reason']
                }
            
            # 计算资金费率成本
            funding_cost_info = await self.strategy_manager.calculate_funding_cost(
                symbol=self.config.TRADING_SYMBOL,
                position_size=trade_signal['trade_amount'],
                hours=24
            )
            
            # 检查资金费率是否过高
            if funding_cost_info['cost_percentage'] > 0.5:
                self.logger.warning(f"资金费率过高 ({funding_cost_info['cost_percentage']:.4f}%), 暂停交易")
                return {
                    'action': 'no_trade',
                    'reason': 'high_funding_cost',
                    'funding_info': funding_cost_info
                }
            
            # 添加资金费率信息到交易信号
            trade_signal['funding_info'] = funding_cost_info
            
            # 执行开仓
            result = await self.trade_executor.open_position(trade_signal)
            
            return result
            
        except Exception as e:
            self.logger.error(f"执行交易失败: {str(e)}")
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
        try:
            # 获取当前持仓
            position = await self.trade_executor.get_current_position()
            
            if not position:
                return {'action': 'no_position'}
            
            # 先检查是否需要平仓
            exit_signal = await self.strategy_manager.check_exit_signal(position, current_price)
            if exit_signal['should_exit']:
                return await self.trade_executor.close_position(exit_signal)
            
            # 如果不需要平仓，检查是否需要更新持仓
            update_signal = await self.strategy_manager.update_position_signal(position, current_price)
            if update_signal['should_update']:
                return await self.trade_executor.update_position_stops(
                    position, 
                    update_signal['new_stop_loss'], 
                    position['take_profit']
                )
            
            return {'action': 'hold_position'}
            
        except Exception as e:
            self.logger.error(f"更新交易状态失败: {str(e)}")
            return {
                'action': 'update_failed',
                'reason': str(e)
            }

    async def refresh_model_data(self) -> None:
        """刷新模型数据"""
        async with self.db_manager.get_session() as session:
            try:
                # 首先检查是否存在get_price_patterns函数
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
                self.logger.info("模型数据已刷新")
                
                # 重新加载策略管理器的模型数据
                await self.strategy_manager.load_model_data()
                
            except Exception as e:
                await session.rollback()
                self.logger.error(f"刷新模型数据时出错: {e}")
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

    async def get_price_history(self, hours: int = 2) -> pd.Series:
        """
        获取价格历史（用于分析前一天的价格模式）
        :param hours: 获取多少小时的数据，默认2小时
        :return: 价格历史Series
        """
        try:
            # 使用OKX API获取K线数据
            kline_data = self.exchange_base.get_candlesticks(
                symbol=self.config.TRADING_SYMBOL,
                bar='1D',  # 2天K线
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
        self.logger.info("交易循环已启动")
        while True:
            try:
                self.logger.info("开始执行交易循环检查...")
                # 获取当前价格和前一天的价格历史（2小时数据）
                current_price = await self.get_current_price()
                price_history = await self.get_price_history(hours=2)
                
                # 获取当前星期几
                day_of_week = datetime.now().strftime('%A')
                
                # 从数据库获取当前持仓
                position = await self.trade_executor.get_current_position()
                
                # 如果没有持仓，检查是否应该开仓
                if not position:
                    self.logger.info("当前无持仓，检查是否应该开仓")
                    await self.execute_trade(current_price, day_of_week, price_history)
                else:
                    # 如果有持仓，更新持仓状态
                    self.logger.info(f"当前有持仓，更新持仓状态: {position}")
                    await self.update_trade(current_price)
                
                self.logger.info("交易循环检查完成，等待10秒后继续...")
                # 每10秒检查一次
                await asyncio.sleep(10)
                
            except Exception as e:
                self.logger.error(f"交易循环错误: {str(e)}")
                self.logger.info("交易循环出错，等待60秒后重试...")
                await asyncio.sleep(60)  # 出错后等待1分钟再继续

    async def run_scheduled_tasks(self) -> None:
        """运行定时任务"""
        self.logger.info("定时任务已启动")
        while True:
            try:
                self.logger.info("开始执行定时任务 - 刷新模型数据...")
                await self.refresh_model_data()
                self.logger.info("模型数据刷新完成")
                
                # 每8小时更新一次模型数据
                next_update = datetime.now() + timedelta(hours=8)
                self.logger.info(f"下次模型数据更新将在: {next_update}")
                await asyncio.sleep(8 * 60 * 60)
                
            except Exception as e:
                self.logger.error(f"定时任务执行错误: {str(e)}")
                self.logger.info("定时任务出错，等待1小时后重试...")
                await asyncio.sleep(3600)  # 出错后等待1小时再继续

    async def run(self) -> None:
        """
        启动系统
        """
        try:
            # 先初始化
            await self.initialize()
            
            if not self.strategy_manager.is_strategy_ready():
                self.logger.error("策略未准备就绪，系统无法启动")
                return
                
            # 启动交易循环和定时任务
            await asyncio.gather(
                self.run_trading_loop(),
                self.run_scheduled_tasks()
            )
        except Exception as e:
            self.logger.error(f"系统启动失败: {str(e)}")
            raise


