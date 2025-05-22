import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, Tuple, Optional, List, Any
import asyncio
from database.dao import TradeStrategyDAO
from exchange.base import ExchangeBase
from config.settings import Config
from database.manager import DatabaseManager

class BitcoinTradingSystem(ExchangeBase):
    def __init__(self, config: Config):
        """
        初始化交易系统
        :param initial_capital: 初始资金
        :param risk_level: 风险等级 (low/medium/high)
        :param db_manager: 数据库管理器
        """
        
        self.position = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        self.config = config
        self.db_manager = DatabaseManager(config.DB_CONFIG)
        self.dao = TradeStrategyDAO(self.db_manager)
        self._initialized_symbols = set()  # 只需要记录是否是首次执行
        self._initialized_swap = set()
        
        # 设置日志
        self.setup_logging()
                
        # 模型数据缓存
        self.pattern_stats = {}
        self.volatility_data = {}
        
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
            self._set_default_model_data()
            return
            
        try:
            # 首先从price_patterns表获取数据（这是已经计算好的数据）
            pattern_data = await self.dao.get_pattern_stats_from_table()
            
            # 如果没有最近的数据，则直接调用get_price_patterns函数计算
            if not pattern_data:
                pattern_data = await self.dao.get_price_patterns()
                
                # 同时更新price_patterns表
                await self.dao.update_price_patterns(pattern_data)
            
            # 处理查询结果，构建pattern_stats和volatility_data字典
            self.pattern_stats = {}
            self.volatility_data = {}
            
            for row in pattern_data:
                day = row['day_of_week']
                pattern = row['pattern_type']
                win_rate = float(row['win_rate'])
                return_rate = float(row['return_rate'])
                volatility = float(row['volatility'])
                
                # 初始化当天的字典（如果不存在）
                if day not in self.pattern_stats:
                    self.pattern_stats[day] = {}
                
                # 添加模式数据
                self.pattern_stats[day][pattern] = {
                    'win_rate': win_rate,
                    'return_rate': return_rate
                }
                
                # 更新波动率数据
                self.volatility_data[day] = max(volatility, self.volatility_data.get(day, 0))
            
            self.logger.info("成功从数据库加载模型数据")
            
            # 如果没有数据，使用默认值
            if not self.pattern_stats:
                self._set_default_model_data()
                
        except Exception as e:
            self.logger.error(f"加载模型数据错误: {str(e)}")
            # 设置默认值
            self._set_default_model_data()

    def _set_default_model_data(self) -> None:
        """设置默认的模型数据"""
        self.pattern_stats = {
            'Sunday': {
                'rise_then_fall': {'win_rate': 0.6125, 'return_rate': 0.0064},
                'continuous_fall': {'win_rate': 0.6036, 'return_rate': 0.0097},
                'fall_then_rise': {'win_rate': 0.4338, 'return_rate': -0.0050}
            },
            'Friday': {
                'continuous_rise': {'win_rate': 0.5669, 'return_rate': 0.0083},
                'rise_then_fall': {'win_rate': 0.5868, 'return_rate': 0.0030}
            },
            'Saturday': {
                'continuous_rise': {'win_rate': 0.4424, 'return_rate': -0.0060}
            }
        }
        self.volatility_data = {
            'Monday': 0.0299,
            'Wednesday': 0.0295,
            'Saturday': 0.0152
        }
        self.logger.warning("使用默认模型数据")

    def analyze_pattern(self, price_history: pd.Series) -> str:
        """
        分析价格模式
        :param price_history: 最近4小时的价格数据
        :return: 价格模式类型
        """
        if len(price_history) < 4:
            return "insufficient_data"
            
        first_half = price_history[:len(price_history)//2]
        second_half = price_history[len(price_history)//2:]
        
        first_trend = first_half[-1] > first_half[0]
        second_trend = second_half[-1] > second_half[0]
        
        if first_trend and not second_trend:
            return "rise_then_fall"
        elif not first_trend and second_trend:
            return "fall_then_rise"
        elif first_trend and second_trend:
            return "continuous_rise"
        else:
            return "continuous_fall"

    def calculate_position_size(self, pattern: str, day: str) -> float:
        """
        计算仓位大小
        :param pattern: 价格模式
        :param day: 星期几
        :return: 建议仓位比例
        """
        if day in self.pattern_stats and pattern in self.pattern_stats[day]:
            stats = self.pattern_stats[day][pattern]
            win_rate = stats['win_rate']
            return_rate = stats['return_rate']
            
            # 使用凯利公式计算基础仓位
            if return_rate > 0:
                kelly = win_rate - ((1 - win_rate) / (return_rate / 0.01))  # 调整收益率单位
                kelly = max(0, kelly)  # 确保凯利值不为负
            else:
                kelly = 0
            
            # 根据风险等级调整
            risk_multiplier = {
                'low': 0.1,
                'medium': 0.25,
                'high': 0.5
            }
            
            return min(kelly * risk_multiplier[self.risk_level], 0.5)
        return 0

    def set_stop_loss(self, price: float, day: str) -> float:
        """
        设置止损价格
        :param price: 当前价格
        :param day: 星期几
        :return: 止损价格
        """
        volatility = self.volatility_data.get(day, 0.02)
        
        if volatility > 0.025:  # 高波动日
            multiplier = 1.5
        elif volatility < 0.02:  # 低波动日
            multiplier = 2.0
        else:  # 中等波动日
            multiplier = 1.8
            
        stop_loss_percentage = volatility * multiplier
        return price * (1 - stop_loss_percentage)

    def should_trade(self, price_history: pd.Series, day: str) -> Tuple[bool, str, float]:
        """
        判断是否应该交易
        :return: (是否交易, 交易方向, 建议仓位比例)
        """
        pattern = self.analyze_pattern(price_history)
        
        # 检查是否是禁止交易的模式
        if (day == 'Saturday' and pattern == 'continuous_rise') or \
           (day == 'Sunday' and pattern == 'fall_then_rise'):
            return False, "none", 0
            
        # 检查是否是优势模式
        if day in self.pattern_stats and pattern in self.pattern_stats[day]:
            stats = self.pattern_stats[day][pattern]
            if stats['win_rate'] > 0.55:
                position_size = self.calculate_position_size(pattern, day)
                return True, "long", position_size
                
        return False, "none", 0

    def execute_trade(self, price: float, day: str, price_history: pd.Series) -> Dict:
        """
        执行交易
        :return: 交易信息
        """
        should_trade, direction, position_size = self.should_trade(price_history, day)
        
        if not should_trade:
            return {
                'action': 'no_trade',
                'reason': 'unfavorable_conditions'
            }
            
        trade_amount = self.capital * position_size
        stop_loss = self.set_stop_loss(price, day)
        take_profit = price * (1 + (price - stop_loss) / price * 1.5)  # 1.5倍风险收益比
        
        self.position = {
            'direction': direction,
            'entry_price': price,
            'size': trade_amount,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': datetime.now(),
            'pattern': self.analyze_pattern(price_history),
            'day': day
        }
        
        self.logger.info(f"Opening trade: {self.position}")
        
        return {
            'action': 'open_trade',
            'details': self.position
        }

    def update_position(self, current_price: float) -> Dict:
        """
        更新持仓状态
        :return: 更新信息
        """
        if not self.position:
            return {'action': 'no_position'}
            
        profit_pct = (current_price - self.position['entry_price']) / self.position['entry_price']
        
        # 移动止损逻辑
        if profit_pct > 0.03:
            new_stop_loss = self.position['entry_price'] * 1.01  # 保本+1%
        elif profit_pct > 0.02:
            new_stop_loss = self.position['entry_price'] * 1.005  # 保本+0.5%
        elif profit_pct > 0.01:
            new_stop_loss = self.position['entry_price']  # 保本
        else:
            new_stop_loss = self.position['stop_loss']
            
        old_stop_loss = self.position['stop_loss']
        self.position['stop_loss'] = max(new_stop_loss, self.position['stop_loss'])
        
        if old_stop_loss != self.position['stop_loss']:
            self.logger.info(f"Updated stop loss: {old_stop_loss} -> {self.position['stop_loss']}")
        
        return {
            'action': 'update_position',
            'new_stop_loss': self.position['stop_loss'],
            'current_profit_pct': profit_pct
        }

    def check_exit_signals(self, current_price: float) -> Dict:
        """
        检查是否应该平仓
        :return: 平仓信息
        """
        if not self.position:
            return {'action': 'no_position'}
            
        if current_price <= self.position['stop_loss']:
            return self.close_position(current_price, 'stop_loss')
            
        if current_price >= self.position['take_profit']:
            return self.close_position(current_price, 'take_profit')
            
        # 检查持仓时间是否过长（超过24小时）
        if datetime.now() - self.position['entry_time'] > timedelta(hours=24):
            return self.close_position(current_price, 'time_limit')
            
        return {'action': 'hold_position'}

    async def close_position(self, price: float, reason: str) -> Dict:
        """
        平仓
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
        
        self.capital += trade_result['profit_amount']
        
        # 记录交易结果到数据库
        if self.db_manager:
            await self.record_trade(trade_result)
        
        self.logger.info(f"Closing trade: {trade_result}")
        self.position = None
        
        return {
            'action': 'close_position',
            'details': trade_result
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
        """
        刷新模型数据
        """
        if not self.db_manager:
            return
            
        try:
            await self.dao.refresh_model_data()
            
            # 重新加载模型数据
            await self.load_model_data()
            
            self.logger.info("模型数据已刷新")
        except Exception as e:
            self.logger.error(f"刷新模型数据时出错: {str(e)}")
