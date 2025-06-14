from typing import Dict, Tuple, Optional, List, Any, TYPE_CHECKING
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

if TYPE_CHECKING:
    from trading.bitcoin_trading_system import BitcoinTradingSystem

class PatternStrategy:
    """基于价格模式的交易策略"""
    
    def __init__(self, trading_system: 'BitcoinTradingSystem'):
        """
        初始化策略
        :param trading_system: BitcoinTradingSystem实例
        """
        self.system: 'BitcoinTradingSystem' = trading_system
        self.logger = trading_system.logger
        
    def analyze_pattern(self, price_history: pd.Series) -> str:
        """
        分析价格模式（基于前一天的数据）
        :param price_history: 前一天的价格数据（至少2个数据点）
        :return: 价格模式类型
        """
        if len(price_history) < 2:
            return "insufficient_data"
        
        # 如果有2个数据点，直接比较前后变化
        if len(price_history) == 2:
            if price_history.iloc[1] > price_history.iloc[0]:
                return "continuous_rise"
            else:
                return "continuous_fall"
        
        # 如果有更多数据点，使用原有的4点分析逻辑
        if len(price_history) >= 4:
            first_half = price_history[:len(price_history)//2]
            second_half = price_history[len(price_history)//2:]
            
            first_trend = first_half.iloc[-1] > first_half.iloc[0]
            second_trend = second_half.iloc[-1] > second_half.iloc[0]
            
            if first_trend and not second_trend:
                return "rise_then_fall"
            elif not first_trend and second_trend:
                return "fall_then_rise"
            elif first_trend and second_trend:
                return "continuous_rise"
            else:
                return "continuous_fall"
        
        # 如果是3个数据点，简化分析
        else:
            first_change = price_history.iloc[1] > price_history.iloc[0]
            second_change = price_history.iloc[2] > price_history.iloc[1]
            
            if first_change and not second_change:
                return "rise_then_fall"
            elif not first_change and second_change:
                return "fall_then_rise"
            elif first_change and second_change:
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
        pattern_stats = self.system.pattern_stats
        if not pattern_stats:
            self.logger.warning("模型数据为空，使用保守仓位")
            return 0.1
            
        risk_level = getattr(self.system.config, 'RISK_LEVEL', 'low')  # 默认使用低风险
        
        if day in pattern_stats and pattern in pattern_stats[day]:
            stats = pattern_stats[day][pattern]
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
            
            return min(kelly * risk_multiplier[risk_level], 0.5)
        return 0.1  # 如果没有该模式的统计数据，使用保守仓位

    def set_stop_loss(self, price: float, day: str) -> float:
        """
        设置止损价格
        :param price: 当前价格
        :param day: 星期几
        :return: 止损价格
        """
        volatility_data = self.system.volatility_data
        if not volatility_data:
            self.logger.warning("波动率数据为空，使用默认波动率")
            return price * 0.98  # 默认2%止损
            
        volatility = volatility_data.get(day, 0.02)
        
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
        if len(price_history) < 2:
            self.logger.warning("价格历史数据不足，需要至少2个数据点")
            return False, "none", 0
            
        pattern = self.analyze_pattern(price_history)
        pattern_stats = self.system.pattern_stats
        
        if not pattern_stats:
            self.logger.warning("模型数据为空，不进行交易")
            return False, "none", 0
        
        # 将英文星期转换为中文
        weekday_map = {
            'Monday': '周一',
            'Tuesday': '周二',
            'Wednesday': '周三',
            'Thursday': '周四',
            'Friday': '周五',
            'Saturday': '周六',
            'Sunday': '周日'
        }
        current_day = weekday_map.get(day, day)  # 当前日期
        
        # 获取前一天的日期（因为next_day_win_rate是指前一天的模式对今天的影响）
        previous_day_map = {
            '周一': '周日',
            '周二': '周一', 
            '周三': '周二',
            '周四': '周三',
            '周五': '周四',
            '周六': '周五',
            '周日': '周六'
        }
        previous_day = previous_day_map.get(current_day, current_day)
        
        # 打印调试信息
        self.logger.info(f"Current day: {current_day}, Previous day: {previous_day}, Pattern: {pattern}")
        self.logger.info(f"Available days in pattern_stats: {list(pattern_stats.keys())}")
        
        # 检查是否是禁止交易的模式（基于前一天的模式）
        if (previous_day == '周五' and pattern == 'continuous_rise') or \
           (previous_day == '周六' and pattern == 'fall_then_rise'):
            self.logger.info(f"Pattern {pattern} from {previous_day} is forbidden for trading on {current_day}")
            return False, "none", 0
            
        # 检查前一天的模式统计数据来预测今天的表现
        if previous_day in pattern_stats and pattern in pattern_stats[previous_day]:
            stats = pattern_stats[previous_day][pattern]
            self.logger.info(f"Found stats for {previous_day}/{pattern}: {stats}")
            if stats['win_rate'] > 0.55:
                position_size = self.calculate_position_size(pattern, previous_day)
                self.logger.info(f"Trading signal: {previous_day} pattern '{pattern}' predicts good performance for {current_day}")
                return True, "long", position_size
            else:
                self.logger.info(f"Win rate {stats['win_rate']} is below threshold 0.55")
        else:
            self.logger.info(f"Pattern {pattern} not found for previous day {previous_day}")
                
        return False, "none", 0

    def update_position(self, position: Dict, current_price: float) -> Dict:
        """
        更新持仓状态
        :param position: 当前持仓信息
        :param current_price: 当前价格
        :return: 更新信息
        """
        if not position:
            return {'action': 'no_position'}
            
        profit_pct = (current_price - position['entry_price']) / position['entry_price']
        
        # 移动止损逻辑
        if profit_pct > 0.03:
            new_stop_loss = position['entry_price'] * 1.01  # 保本+1%
        elif profit_pct > 0.02:
            new_stop_loss = position['entry_price'] * 1.005  # 保本+0.5%
        elif profit_pct > 0.01:
            new_stop_loss = position['entry_price']  # 保本
        else:
            new_stop_loss = position['stop_loss']
            
        old_stop_loss = position['stop_loss']
        position['stop_loss'] = max(new_stop_loss, position['stop_loss'])
        
        if old_stop_loss != position['stop_loss']:
            self.logger.info(f"Updated stop loss: {old_stop_loss} -> {position['stop_loss']}")
        
        return {
            'action': 'update_position',
            'position': position,
            'new_stop_loss': position['stop_loss'],
            'current_profit_pct': profit_pct
        }

    def check_exit_signals(self, position: Dict, current_price: float) -> Dict:
        """
        检查是否应该平仓
        :param position: 当前持仓信息
        :param current_price: 当前价格
        :return: 平仓信息
        """
        if not position:
            return {'action': 'no_position'}
            
        if current_price <= position['stop_loss']:
            return {'action': 'close_position', 'reason': 'stop_loss'}
            
        if current_price >= position['take_profit']:
            return {'action': 'close_position', 'reason': 'take_profit'}
            
        # 检查持仓时间是否过长（超过24小时）
        if datetime.now() - position['entry_time'] > timedelta(hours=24):
            return {'action': 'close_position', 'reason': 'time_limit'}
            
        return {'action': 'hold_position'}
