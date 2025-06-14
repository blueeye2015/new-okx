from typing import Dict, Tuple, Optional, Any
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from strategies.pattern_strategy import PatternStrategy
from database.dao import TradeStrategyDAO
from exchange.base import ExchangeBase
from config.settings import Config


class StrategyManager:
    """策略管理器 - 负责策略逻辑和信号生成"""
    
    def __init__(self, config: Config, dao: TradeStrategyDAO, exchange_base: ExchangeBase):
        """
        初始化策略管理器
        :param config: 配置对象
        :param dao: 数据访问对象
        :param exchange_base: 交易所接口
        """
        self.config = config
        self.dao = dao
        self.exchange_base = exchange_base
        self.logger = logging.getLogger('StrategyManager')
        
        # 模型数据缓存
        self.pattern_stats = {}
        self.volatility_data = {}
        
        # 策略对象
        self.strategy = None
        
        # 风险参数
        self.risk_params = {
            'conservative': {
                'max_leverage': 2,
                'max_position_pct': 0.2,
                'stop_loss_pct': 0.04,
                'margin_buffer': 0.2
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
    
    async def initialize_strategy(self):
        """初始化策略"""
        try:
            # 加载模型数据
            await self.load_model_data()
            
            # 初始化策略对象
            self.strategy = PatternStrategy(self)
            self.logger.info("策略初始化完成")
            
        except Exception as e:
            self.logger.error(f"策略初始化失败: {str(e)}")
            raise
    
    async def load_model_data(self):
        """加载模型数据"""
        try:
            # 从数据库加载模型数据
            pattern_data = await self.dao.get_pattern_stats_from_table()
            
            if not pattern_data:
                self.logger.warning("无法从数据库获取模型数据，尝试刷新模型数据...")
                await self.dao.refresh_model_data()
                pattern_data = await self.dao.get_pattern_stats_from_table()
                
                if not pattern_data:
                    raise ValueError("无法获取或生成模型数据")
            
            # 处理数据
            self.pattern_stats = {}
            self.volatility_data = {}
            
            for row in pattern_data:
                day = row['week_period']
                pattern = row['pattern']
                
                if day not in self.pattern_stats:
                    self.pattern_stats[day] = {}
                    
                self.pattern_stats[day][pattern] = {
                    'win_rate': float(row['next_day_win_rate']) / 100,
                    'return_rate': float(row['avg_next_return']) / 100,
                    'cases': int(row['cases'])
                }
                
                # 更新波动率数据
                self.volatility_data[day] = float(row['avg_movement']) / 100
            
            self.logger.info("模型数据加载完成")
            
        except Exception as e:
            self.logger.error(f"加载模型数据失败: {str(e)}")
            raise
    
    async def generate_trade_signal(self, price: float, day: str, price_history: pd.Series) -> Dict:
        """
        生成交易信号
        :param price: 当前价格
        :param day: 星期几
        :param price_history: 价格历史
        :return: 交易信号
        """
        try:
            if not self.strategy:
                return {
                    'should_trade': False,
                    'reason': 'strategy_not_initialized'
                }
            
            # 使用策略判断是否应该交易
            should_trade, direction, position_size = self.strategy.should_trade(price_history, day)
            
            if not should_trade:
                return {
                    'should_trade': False,
                    'reason': 'unfavorable_conditions'
                }
            
            # 获取账户余额
            balance = self.exchange_base.get_balance()
            trade_amount = balance * position_size
            
            # 设置止损和止盈
            stop_loss = self.strategy.set_stop_loss(price, day)
            take_profit = price * (1 + (price - stop_loss) / price * 1.5)
            
            # 计算BTC数量
            btc_amount = trade_amount / price
            
            # 分析价格模式
            pattern = self.strategy.analyze_pattern(price_history)
            
            trade_signal = {
                'should_trade': True,
                'direction': direction,
                'entry_price': price,
                'trade_amount': trade_amount,
                'btc_amount': btc_amount,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'position_size_pct': position_size,
                'pattern': pattern,
                'day': day,
                'balance': balance,
                'risk_reward_ratio': 1.5
            }
            
            self.logger.info(f"生成交易信号: {trade_signal}")
            return trade_signal
            
        except Exception as e:
            self.logger.error(f"生成交易信号失败: {str(e)}")
            return {
                'should_trade': False,
                'reason': 'signal_generation_error',
                'error': str(e)
            }
    
    async def check_exit_signal(self, position: Dict, current_price: float) -> Dict:
        """
        检查平仓信号
        :param position: 当前持仓
        :param current_price: 当前价格
        :return: 平仓信号
        """
        try:
            if not position:
                return {'should_exit': False, 'reason': 'no_position'}
            
            if not self.strategy:
                return {'should_exit': False, 'reason': 'strategy_not_initialized'}
            
            # 使用策略检查平仓信号
            exit_signal = self.strategy.check_exit_signals(position, current_price)
            
            if exit_signal['action'] == 'close_position':
                return {
                    'should_exit': True,
                    'reason': exit_signal['reason'],
                    'exit_price': current_price
                }
            
            return {'should_exit': False, 'reason': 'hold_position'}
            
        except Exception as e:
            self.logger.error(f"检查平仓信号失败: {str(e)}")
            return {
                'should_exit': False,
                'reason': 'exit_signal_error',
                'error': str(e)
            }
    
    async def update_position_signal(self, position: Dict, current_price: float) -> Dict:
        """
        生成持仓更新信号
        :param position: 当前持仓
        :param current_price: 当前价格
        :return: 更新信号
        """
        try:
            if not position or not self.strategy:
                return {'should_update': False}
            
            # 使用策略更新持仓
            update_result = self.strategy.update_position(position, current_price)
            
            if update_result['action'] == 'update_position':
                return {
                    'should_update': True,
                    'new_stop_loss': update_result['new_stop_loss'],
                    'current_profit_pct': update_result['current_profit_pct'],
                    'updated_position': update_result['position']
                }
            
            return {'should_update': False}
            
        except Exception as e:
            self.logger.error(f"生成持仓更新信号失败: {str(e)}")
            return {
                'should_update': False,
                'error': str(e)
            }
    
    async def calculate_funding_cost(self, symbol: str, position_size: float, hours: int = 24) -> Dict:
        """
        计算资金费率成本
        :param symbol: 交易对符号
        :param position_size: 持仓大小
        :param hours: 时间范围
        :return: 资金费率成本信息
        """
        try:
            # 使用DAO获取资金费率数据
            funding_records = await self.dao.get_funding_cost_data(symbol, hours)
            
            if not funding_records:
                self.logger.warning(f"未找到 {symbol} 的资金费率数据")
                return {
                    'total_cost': 0.0,
                    'average_rate': 0.0,
                    'periods_count': 0,
                    'estimated_daily_cost': 0.0,
                    'cost_percentage': 0.0
                }
            
            # 计算资金费率成本
            total_funding_cost = 0.0
            total_funding_rate = 0.0
            periods_count = len(funding_records)
            
            for record in funding_records:
                funding_rate = float(record['fundingRate'])
                period_cost = position_size * funding_rate
                total_funding_cost += period_cost
                total_funding_rate += funding_rate
            
            # 计算平均费率和其他指标
            average_rate = total_funding_rate / periods_count if periods_count > 0 else 0.0
            periods_per_day = 3
            estimated_daily_cost = average_rate * position_size * periods_per_day
            cost_percentage = (total_funding_cost / position_size * 100) if position_size > 0 else 0.0
            
            funding_cost_info = {
                'total_cost': round(total_funding_cost, 6),
                'average_rate': round(average_rate, 8),
                'periods_count': periods_count,
                'estimated_daily_cost': round(estimated_daily_cost, 6),
                'cost_percentage': round(cost_percentage, 4),
                'latest_rate': float(funding_records[0]['fundingRate']) if funding_records else 0.0,
                'latest_time': funding_records[0]['fundingTime'] if funding_records else None
            }
            
            return funding_cost_info
            
        except Exception as e:
            self.logger.error(f"计算资金费率成本失败: {str(e)}")
            return {
                'total_cost': 0.0,
                'average_rate': 0.0,
                'periods_count': 0,
                'estimated_daily_cost': 0.0,
                'cost_percentage': 0.0,
                'error': str(e)
            }
    
    def get_risk_parameters(self, risk_level: str = 'conservative') -> Dict:
        """
        获取风险参数
        :param risk_level: 风险等级
        :return: 风险参数
        """
        return self.risk_params.get(risk_level, self.risk_params['conservative'])
    
    def is_strategy_ready(self) -> bool:
        """检查策略是否准备就绪"""
        return self.strategy is not None and bool(self.pattern_stats)
    
    def get_strategy_stats(self) -> Dict:
        """获取策略统计信息"""
        return {
            'pattern_stats': self.pattern_stats,
            'volatility_data': self.volatility_data,
            'strategy_initialized': self.strategy is not None,
            'patterns_count': sum(len(patterns) for patterns in self.pattern_stats.values()),
            'days_covered': list(self.pattern_stats.keys())
        } 