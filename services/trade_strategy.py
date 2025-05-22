import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, Tuple, Optional, List
import time
import psycopg2
from psycopg2.extras import RealDictCursor

class BitcoinTradingSystem:
    def __init__(self, initial_capital: float, risk_level: str = 'medium', db_config: Dict = None):
        """
        初始化交易系统
        :param initial_capital: 初始资金
        :param risk_level: 风险等级 (low/medium/high)
        :param db_config: 数据库连接配置
        """
        self.capital = initial_capital
        self.risk_level = risk_level
        self.position = None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        self.db_config = db_config or {
            'host': 'localhost',
            'database': 'market_data',
            'user': 'postgres',
            'password': '12'
        }
        
        # 设置日志
        self.setup_logging()
        
        # 初始化数据库连接
        self._init_database()
        
        # 模型数据缓存
        self.pattern_stats = {}
        self.volatility_data = {}
        
        # 加载模型数据
        self.load_model_data()

    def setup_logging(self):
        """设置日志系统"""
        logging.basicConfig(
            filename=f'trading_log_{datetime.now().strftime("%Y%m%d")}.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('BitcoinTrader')

    def _init_database(self) -> None:
        """初始化数据库连接并检查必要的表和函数"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 检查get_price_patterns函数是否存在
            cursor.execute("""
            SELECT routine_name FROM information_schema.routines 
            WHERE routine_type = 'FUNCTION' AND routine_name = 'get_price_patterns'
            """)
            
            if cursor.fetchone() is None:
                self._create_database_schema(cursor)
                
            conn.commit()
            cursor.close()
            conn.close()
            self.logger.info("数据库初始化成功")
        except Exception as e:
            self.logger.error(f"数据库初始化失败: {e}")
            raise

    def _create_database_schema(self, cursor) -> None:
        """创建必要的数据库表和函数"""
        try:
            # 创建交易历史表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id SERIAL PRIMARY KEY,
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP NOT NULL,
                entry_price DECIMAL(18, 2) NOT NULL,
                exit_price DECIMAL(18, 2) NOT NULL,
                profit_pct DECIMAL(8, 4) NOT NULL,
                profit_amount DECIMAL(18, 2) NOT NULL,
                day_of_week TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                exit_reason TEXT NOT NULL
            );
            """)
            
            # 创建价格模式统计表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_patterns (
                id SERIAL PRIMARY KEY,
                day_of_week TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                win_rate DECIMAL(8, 4) NOT NULL,
                return_rate DECIMAL(8, 4) NOT NULL,
                volatility DECIMAL(8, 4) NOT NULL,
                sample_size INT NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                UNIQUE(day_of_week, pattern_type)
            );
            """)
            
            # 创建价格模式统计函数
            cursor.execute("""
            CREATE OR REPLACE FUNCTION get_price_patterns()
            RETURNS TABLE (
                day_of_week TEXT,
                pattern_type TEXT,
                win_rate FLOAT,
                return_rate FLOAT,
                volatility FLOAT,
                sample_size INT
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT 
                    th.day_of_week,
                    th.pattern_type,
                    COUNT(CASE WHEN th.profit_pct > 0 THEN 1 END)::FLOAT / COUNT(*)::FLOAT AS win_rate,
                    AVG(th.profit_pct) AS return_rate,
                    STDDEV(th.profit_pct) AS volatility,
                    COUNT(*) AS sample_size
                FROM 
                    trade_history th
                WHERE 
                    th.entry_time >= NOW() - INTERVAL '6 months'
                GROUP BY 
                    th.day_of_week, th.pattern_type
                HAVING 
                    COUNT(*) >= 20;  -- 确保样本量足够
            END;
            $$ LANGUAGE plpgsql;
            """)
            
            # 创建索引以提高查询性能
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_history_entry_time ON trade_history(entry_time);
            CREATE INDEX IF NOT EXISTS idx_price_patterns_day_pattern ON price_patterns(day_of_week, pattern_type);
            """)
            
            self.logger.info("数据库架构创建成功")
        except Exception as e:
            self.logger.error(f"创建数据库架构失败: {e}")
            raise

    def load_model_data(self) -> None:
        """从数据库加载模型数据"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 首先从price_patterns表获取数据（这是已经计算好的数据）
            cursor.execute("""
            SELECT day_of_week, pattern_type, win_rate, return_rate, volatility, sample_size
            FROM price_patterns
            WHERE updated_at >= NOW() - INTERVAL '1 day'
            """)
            
            pattern_data = cursor.fetchall()
            
            # 如果没有最近的数据，则直接调用get_price_patterns函数计算
            if not pattern_data:
                cursor.execute("SELECT * FROM get_price_patterns();")
                pattern_data = cursor.fetchall()
                
                # 同时更新price_patterns表
                self._update_price_patterns(pattern_data)
            
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
            
            cursor.close()
            conn.close()
            
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

    def _update_price_patterns(self, pattern_data: List[Dict]) -> None:
        """更新价格模式统计表"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            for row in pattern_data:
                cursor.execute("""
                INSERT INTO price_patterns (
                    day_of_week, pattern_type, win_rate, return_rate, volatility, sample_size, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (day_of_week, pattern_type) 
                DO UPDATE SET
                    win_rate = EXCLUDED.win_rate,
                    return_rate = EXCLUDED.return_rate,
                    volatility = EXCLUDED.volatility,
                    sample_size = EXCLUDED.sample_size,
                    updated_at = NOW()
                """, (
                    row['day_of_week'],
                    row['pattern_type'],
                    row['win_rate'],
                    row['return_rate'],
                    row['volatility'],
                    row['sample_size']
                ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info("价格模式统计表已更新")
        except Exception as e:
            self.logger.error(f"更新价格模式统计表失败: {e}")

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
            'exit_reason': reason,
            'pattern': self.position['pattern'],
            'day': self.position['day']
        }
        
        self.capital += trade_result['profit_amount']
        
        # 记录交易结果到数据库
        self.record_trade(trade_result)
        
        self.logger.info(f"Closing trade: {trade_result}")
        self.position = None
        
        return {
            'action': 'close_position',
            'details': trade_result
        }
        
    def record_trade(self, trade_result: Dict) -> None:
        """
        记录交易结果到数据库
        :param trade_result: 交易结果
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO trade_history (
                    entry_time, exit_time, entry_price, exit_price, 
                    profit_pct, profit_amount, day_of_week, pattern_type, exit_reason
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                self.position['entry_time'],
                datetime.now(),
                trade_result['entry_price'],
                trade_result['exit_price'],
                trade_result['profit_pct'],
                trade_result['profit_amount'],
                trade_result['day'],
                trade_result['pattern'],
                trade_result['exit_reason']
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info("交易记录已保存到数据库")
            
            # 如果交易记录超过一定数量，更新模型数据
            if self._should_update_model():
                self.refresh_model_data()
                
        except Exception as e:
            self.logger.error(f"记录交易错误: {str(e)}")

    def _should_update_model(self) -> bool:
        """判断是否应该更新模型数据"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 检查最近一小时内的交易记录数量
            cursor.execute("""
            SELECT COUNT(*) FROM trade_history
            WHERE exit_time >= NOW() - INTERVAL '1 hour'
            """)
            
            recent_trades = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            # 如果最近一小时有超过5笔交易，更新模型
            return recent_trades >= 5
            
        except Exception as e:
            self.logger.error(f"检查是否应更新模型时出错: {str(e)}")
            return False

    def refresh_model_data(self) -> None:
        """
        刷新模型数据
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 执行get_price_patterns函数并将结果存储到price_patterns表中
            cursor.execute("""
            INSERT INTO price_patterns (
                day_of_week, pattern_type, win_rate, return_rate, volatility, sample_size, updated_at
            )
            SELECT 
                day_of_week, pattern_type, win_rate, return_rate, volatility, sample_size, NOW()
            FROM 
                get_price_patterns()
            ON CONFLICT (day_of_week, pattern_type) 
            DO UPDATE SET
                win_rate = EXCLUDED.win_rate,
                return_rate = EXCLUDED.return_rate,
                volatility = EXCLUDED.volatility,
                sample_size = EXCLUDED.sample_size,
                updated_at = NOW();
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            # 重新加载模型数据
            self.load_model_data()
            
            self.logger.info("模型数据已刷新")
        except Exception as e:
            self.logger.error(f"刷新模型数据时出错: {str(e)}")
