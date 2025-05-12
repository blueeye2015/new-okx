import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, Tuple, Optional
import time

class BitcoinTradingSystem:
    def __init__(self, initial_capital: float, risk_level: str = 'medium'):
        """
        初始化交易系统
        :param initial_capital: 初始资金
        :param risk_level: 风险等级 (low/medium/high)
        """
        self.capital = initial_capital
        self.risk_level = risk_level
        self.position = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        
        # 统计模型数据
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
        
        # 波动率数据
        self.volatility_data = {
            'Monday': 0.0299,
            'Wednesday': 0.0295,
            'Saturday': 0.0152
        }
        
        # 设置日志
        self.setup_logging()

    def setup_logging(self):
        """设置日志系统"""
        logging.basicConfig(
            filename=f'trading_log_{datetime.now().strftime("%Y%m%d")}.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('BitcoinTrader')

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
            kelly = win_rate - ((1 - win_rate) / return_rate)
            
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
            'entry_time': datetime.now()
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
            
        self.position['stop_loss'] = max(new_stop_loss, self.position['stop_loss'])
        
        return {
            'action': 'update_position',
            'new_stop_loss': self.position['stop_loss']
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
            
        return {'action': 'hold_position'}

    def close_position(self, price: float, reason: str) -> Dict:
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
            'entry_price': self.position['entry_price'],
            'exit_price': price,
            'profit_pct': profit_pct,
            'profit_amount': profit * self.position['size'],
            'hold_time': datetime.now() - self.position['entry_time'],
            'exit_reason': reason
        }
        
        self.capital += trade_result['profit_amount']
        self.position = None
        
        self.logger.info(f"Closing trade: {trade_result}")
        
        return {
            'action': 'close_position',
            'details': trade_result
        }

