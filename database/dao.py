from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.future import select
from database.models import KlineModel,FundingRateModel
from models.kline import Kline
from models.fundingrate import Fundingrate
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import time
from functools import wraps
import asyncio
from sqlalchemy.sql import text

def async_timer(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        task_id = id(asyncio.current_task())
        logging.info(f"Starting task {func.__name__} (ID: {task_id})")
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start
            logging.info(f"Task {func.__name__} (ID: {task_id}) completed in {elapsed:.2f} seconds")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logging.error(f"Task {func.__name__} (ID: {task_id}) failed after {elapsed:.2f} seconds: {str(e)}")
            raise
    return wrapper


class BaseDAO(ABC):
    def __init__(self, db_manager):
        self.db_manager = db_manager
    
    @abstractmethod
    async def create_table(self): pass
    
    @abstractmethod
    async def insert(self, data): pass
    
    @abstractmethod
    async def query(self, **kwargs): pass

class FundingrateDAO(BaseDAO):
    async def create_table(self):
        pass
    
    #@async_timer
    async def insert(self, fundingrate: Fundingrate):
        """插入单条数据"""
        async with self.db_manager.get_session() as session:
            try:
                fundingrate_model = FundingRateModel(
                    symbol=fundingrate.symbol,
                    fundingTime=fundingrate.fundingTime,
                    fundingRate=fundingrate.fundingRate,
                    realizedRate=fundingrate.realizedRate,
                    method=fundingrate.method
                )
                
                stmt = insert(FundingRateModel).values(
                    vars(fundingrate_model)
                ).on_conflict_do_update(
                    index_elements=['symbol', 'fundingTime'],
                    set_={
                        'fundingRate': fundingrate_model.fundingRate,
                        'realizedRate': fundingrate_model.realizedRate,
                        'method': fundingrate_model.method
                    }
                )
                
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()
    
    #@async_timer
    async def save_fundingrate(self, fundingrate_model: List[Fundingrate]):
        if not fundingrate_model:
            return
        async with self.db_manager.get_session() as session:
            try:
                # 使用批量插入
                values = [{
                    'symbol': model.symbol,
                    'fundingTime': model.fundingTime,
                    'fundingRate': model.fundingRate,
                    'realizedRate': model.realizedRate,
                    'method': model.method
                } for model in fundingrate_model]
                
                await session.execute(
                    text("""
                    INSERT INTO Fundingrate (symbol, fundingTime, fundingRate, realizedRate, method)
                    VALUES (:symbol, :fundingTime, :fundingRate, :realizedRate, :method)
                    ON CONFLICT (symbol, fundingTime) DO UPDATE SET
                        fundingRate = EXCLUDED.fundingRate,
                        realizedRate = EXCLUDED.realizedRate,
                        method = EXCLUDED.method
                    """),
                    values
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
    
    #@async_timer
    async def get_latest_kline(self):
        """获取指定交易对的最新K线数据（同步方式）"""
        pass
           
    #@async_timer
    async def query(self) :
        """查询数据"""
        pass

class KlineDAO(BaseDAO):
    async def create_table(self):
        pass
    
    #@async_timer
    async def insert(self, kline: Kline):
        """插入单条数据"""
        async with self.db_manager.get_session() as session:
            try:
                kline_model = KlineModel(
                    symbol=kline.symbol,
                    timestamp=kline.timestamp,
                    open=kline.open,
                    high=kline.high,
                    low=kline.low,
                    close=kline.close,
                    volume=kline.volume
                )
                
                stmt = insert(KlineModel).values(
                    vars(kline_model)
                ).on_conflict_do_update(
                    index_elements=['symbol', 'timestamp'],
                    set_={
                        'open': kline_model.open,
                        'high': kline_model.high,
                        'low': kline_model.low,
                        'close': kline_model.close,
                        'volume': kline_model.volume
                    }
                )
                
                await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
            finally:
                await session.close()
    
    #@async_timer
    async def save_klines(self, kline_models: List[Kline]):
        if not kline_models:
            return
        async with self.db_manager.get_session() as session:
            try:
                # 使用批量插入
                values = [{
                    'symbol': model.symbol,
                    'timestamp': model.timestamp,
                    'open_price': model.open,
                    'high_price': model.high,
                    'low_price': model.low,
                    'close_price': model.close,
                    'volume': model.volume,
                    'volume_currency': model.vol_ccy,
                    'volume_currency_quote': model.vol_quote,
                    'is_confirmed': model.confirm == '1'  # 转换为布尔值
                } for model in kline_models]
                
                await session.execute(
                    text("""
                    INSERT INTO kline_data (
                        symbol, timestamp, open_price, high_price, low_price, close_price,
                        volume, volume_currency, volume_currency_quote, is_confirmed
                    )
                    VALUES (
                        :symbol, :timestamp, :open_price, :high_price, :low_price, :close_price,
                        :volume, :volume_currency, :volume_currency_quote, :is_confirmed
                    )
                    ON CONFLICT (symbol, timestamp) DO UPDATE SET
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        close_price = EXCLUDED.close_price,
                        volume = EXCLUDED.volume,
                        volume_currency = EXCLUDED.volume_currency,
                        volume_currency_quote = EXCLUDED.volume_currency_quote,
                        is_confirmed = EXCLUDED.is_confirmed
                    """),
                    values
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
    
    #@async_timer
    async def get_latest_kline(self, symbol: str) -> Optional[Kline]:
        """获取指定交易对的最新K线数据"""
        async with self.db_manager.get_session() as session:
            try:
                stmt = select(KlineModel).filter(
                    KlineModel.symbol == symbol
                ).order_by(
                    KlineModel.timestamp.desc()
                ).limit(1)
                
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                
                if row:
                    return Kline(
                        symbol=row.symbol,
                        timestamp=row.timestamp,
                        open=float(row.open_price),
                        high=float(row.high_price),
                        low=float(row.low_price),
                        close=float(row.close_price),
                        volume=float(row.volume),
                        vol_ccy=float(row.volume_currency),
                        vol_quote=float(row.volume_currency_quote),
                        confirm='1' if row.is_confirmed else '0'
                    )
                return None
                
            except Exception as e:
                logging.error(f"获取最新K线数据失败: {e}")
                raise
           
    #@async_timer
    async def query(self, symbol: str = None, 
              start_time: datetime = None, 
              end_time: datetime = None) -> List[Kline]:
        """查询数据"""
        async with self.db_manager.get_session() as session:
            query = select(KlineModel)
            
            
            if symbol:
                query = query.filter(KlineModel.symbol == symbol)
            if start_time:
                query = query.filter(KlineModel.timestamp >= start_time)
            if end_time:
                query = query.filter(KlineModel.timestamp <= end_time)
                
            query = query.order_by(KlineModel.timestamp)
            
            return [
                Kline(
                    symbol=row.symbol,
                    timestamp=row.timestamp,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume
                ) for row in query.all()
            ]
        

class TradeStrategyDAO(BaseDAO):
    @async_timer
    async def create_table(self):
        """创建必要的数据库表"""
        async with self.db_manager.get_session() as session:
            # 创建活跃持仓表
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS active_positions (
                    id SERIAL PRIMARY KEY,
                    direction VARCHAR(10) NOT NULL,
                    entry_price DECIMAL(20, 8) NOT NULL,
                    size DECIMAL(20, 8) NOT NULL,
                    stop_loss DECIMAL(20, 8) NOT NULL,
                    take_profit DECIMAL(20, 8) NOT NULL,
                    entry_time TIMESTAMP NOT NULL,
                    pattern VARCHAR(50),
                    day_of_week VARCHAR(20),
                    instrument_id VARCHAR(50) DEFAULT 'BTC-USDT-SWAP',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """))
            
            # 添加instrument_id字段（如果表已存在但没有该字段）
            await session.execute(text("""
                ALTER TABLE active_positions 
                ADD COLUMN IF NOT EXISTS instrument_id VARCHAR(50) DEFAULT 'BTC-USDT-SWAP';
            """))
            await session.commit()

    @async_timer
    async def get_price_patterns(self) -> List[Dict]:
        """获取价格模式统计数据"""
        async with self.db_manager.get_session() as session:
            try:
                result = await session.execute(text("SELECT * FROM get_price_patterns();"))
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows] if rows else []
            except Exception as e:
                logging.error(f"获取价格模式统计数据失败: {e}")
                return []
    
    @async_timer
    async def get_pattern_stats_from_table(self) -> List[Dict]:
        """从price_patterns表获取价格模式统计数据"""
        async with self.db_manager.get_session() as session:
            try:
                result = await session.execute(text("""
                SELECT week_period, pattern, cases, avg_next_return, 
                    next_day_win_rate, avg_current_return, avg_movement
                FROM price_patterns
                WHERE updated_at >= NOW() - INTERVAL '1 day'
                """))
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows] if rows else []
            except Exception as e:
                logging.error(f"从price_patterns表获取价格模式统计数据失败: {e}")
                return []
    
    @async_timer
    async def update_price_patterns(self, pattern_data: List[Dict]) -> None:
        """更新价格模式统计表"""
        if not pattern_data:
            return
            
        async with self.db_manager.get_session() as session:
            try:
                for row in pattern_data:
                    await session.execute(text("""
                    INSERT INTO price_patterns (
                        week_period, pattern, cases, avg_next_return, 
                        next_day_win_rate, avg_current_return, avg_movement, updated_at
                    ) VALUES (
                        :week_period, :pattern, :cases, :avg_next_return, 
                        :next_day_win_rate, :avg_current_return, :avg_movement, NOW()
                    )
                    ON CONFLICT (week_period, pattern) 
                    DO UPDATE SET
                        cases = EXCLUDED.cases,
                        avg_next_return = EXCLUDED.avg_next_return,
                        next_day_win_rate = EXCLUDED.next_day_win_rate,
                        avg_current_return = EXCLUDED.avg_current_return,
                        avg_movement = EXCLUDED.avg_movement,
                        updated_at = NOW()
                    """), row)
                
                await session.commit()
                logging.info("价格模式统计表已更新")
            except Exception as e:
                await session.rollback()
                logging.error(f"更新价格模式统计表失败: {e}")
                raise e
    
    @async_timer
    async def record_trade(self, trade_data: Dict) -> None:
        """记录交易结果到数据库"""
        async with self.db_manager.get_session() as session:
            try:
                await session.execute(text("""
                INSERT INTO trade_history (
                    entry_time, exit_time, entry_price, exit_price, 
                    profit_pct, profit_amount, day_of_week, pattern_type, exit_reason
                ) VALUES (
                    :entry_time, :exit_time, :entry_price, :exit_price, 
                    :profit_pct, :profit_amount, :day_of_week, :pattern_type, :exit_reason
                )
                """), trade_data)
                
                await session.commit()
                logging.info("交易记录已保存到数据库")
            except Exception as e:
                await session.rollback()
                logging.error(f"记录交易错误: {e}")
                raise e
    
    @async_timer
    async def should_update_model(self) -> bool:
        """判断是否应该更新模型数据"""
        async with self.db_manager.get_session() as session:
            try:
                result = await session.execute(text("""
                SELECT COUNT(*) FROM trade_history
                WHERE exit_time >= NOW() - INTERVAL '1 hour'
                """))
                recent_trades = result.scalar()
                
                # 如果最近一小时有超过5笔交易，更新模型
                return recent_trades >= 5
            except Exception as e:
                logging.error(f"检查是否应更新模型时出错: {e}")
                return False
    
    @async_timer
    async def refresh_model_data(self) -> None:
        """刷新模型数据"""
        async with self.db_manager.get_session() as session:
            try:
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
                
                await session.commit()
                logging.info("模型数据已刷新")
            except Exception as e:
                await session.rollback()
                logging.error(f"刷新模型数据时出错: {e}")
                raise e
                
    async def insert(self, data):
        """实现抽象方法"""
        pass
        
    async def query(self, **kwargs):
        """实现抽象方法"""
        pass

    async def get_active_position(self) -> Optional[Dict]:
        """获取当前活跃的持仓（从交易所API获取实时数据）"""
        try:
            from exchange.base import ExchangeBase
            
            # 使用交易所API获取实时持仓信息
            exchange = ExchangeBase()
            account_info = exchange.get_account_info()
            
            positions_data = account_info.get('positions', {})
            
            # 检查是否有持仓数据
            if positions_data and 'data' in positions_data and positions_data['data']:
                for position in positions_data['data']:
                    # 检查是否有实际持仓（持仓量不为0）
                    pos_size = float(position.get('pos', 0))
                    if pos_size != 0:
                        # 从数据库获取对应的策略信息（如果存在）
                        strategy_info = await self._get_position_strategy_info(position.get('instId'))
                        
                        return {
                            'direction': 'long' if pos_size > 0 else 'short',
                            'entry_price': float(position.get('avgPx', 0)),
                            'size': abs(pos_size),
                            'stop_loss': strategy_info.get('stop_loss', 0) if strategy_info else 0,
                            'take_profit': strategy_info.get('take_profit', 0) if strategy_info else 0,
                            'entry_time': strategy_info.get('entry_time') if strategy_info else None,
                            'pattern': strategy_info.get('pattern', 'unknown') if strategy_info else 'unknown',
                            'day': strategy_info.get('day', 'unknown') if strategy_info else 'unknown',
                            'instrument_id': position.get('instId'),
                            'unrealized_pnl': float(position.get('upl', 0)),
                            'margin': float(position.get('margin', 0)),
                            'mark_price': float(position.get('markPx', 0))
                        }
            
            return None
            
        except Exception as e:
            logging.error(f"从交易所API获取持仓信息失败: {e}")
            # 如果API调用失败，回退到数据库查询
            return await self._get_active_position_from_db()

    async def _get_position_strategy_info(self, instrument_id: str) -> Optional[Dict]:
        """从数据库获取持仓的策略信息"""
        async with self.db_manager.get_session() as session:
            try:
                result = await session.execute(text("""
                    SELECT stop_loss, take_profit, entry_time, pattern, day_of_week
                    FROM active_positions 
                    WHERE instrument_id = :instrument_id
                    ORDER BY entry_time DESC 
                    LIMIT 1
                """), {'instrument_id': instrument_id})
                
                strategy_data = result.fetchone()
                if strategy_data:
                    return {
                        'stop_loss': float(strategy_data.stop_loss),
                        'take_profit': float(strategy_data.take_profit),
                        'entry_time': strategy_data.entry_time,
                        'pattern': strategy_data.pattern,
                        'day': strategy_data.day_of_week
                    }
                return None
            except Exception as e:
                logging.error(f"获取策略信息失败: {e}")
                return None

    async def _get_active_position_from_db(self) -> Optional[Dict]:
        """从数据库获取当前活跃的持仓（备用方法）"""
        async with self.db_manager.get_session() as session:
            result = await session.execute(text("""
                SELECT * FROM active_positions 
                ORDER BY entry_time DESC 
                LIMIT 1
            """))
            position = result.fetchone()
            
            if position:
                # 将SQLAlchemy Row对象转换为字典
                return {
                    'direction': position.direction,
                    'entry_price': float(position.entry_price),
                    'size': float(position.size),
                    'stop_loss': float(position.stop_loss),
                    'take_profit': float(position.take_profit),
                    'entry_time': position.entry_time,
                    'pattern': position.pattern,
                    'day': position.day_of_week
                }
            return None

    async def save_position(self, position: Dict) -> None:
        """保存新的持仓信息"""
        async with self.db_manager.get_session() as session:
            # 先清除之前的持仓记录
            await session.execute(text("DELETE FROM active_positions"))
            
            # 插入新的持仓记录
            await session.execute(text("""
                INSERT INTO active_positions (
                    direction, entry_price, size, stop_loss, take_profit,
                    entry_time, pattern, day_of_week, instrument_id
                ) VALUES (
                    :direction, :entry_price, :size, :stop_loss, :take_profit,
                    :entry_time, :pattern, :day, :instrument_id
                )
            """), {
                'direction': position['direction'],
                'entry_price': position['entry_price'],
                'size': position['size'],
                'stop_loss': position['stop_loss'],
                'take_profit': position['take_profit'],
                'entry_time': position['entry_time'],
                'pattern': position['pattern'],
                'day': position['day'],
                'instrument_id': position.get('instrument_id', 'BTC-USDT-SWAP')  # 默认值
            })
            await session.commit()

    async def update_position(self, position: Dict) -> None:
        """更新持仓信息"""
        async with self.db_manager.get_session() as session:
            await session.execute(text("""
                UPDATE active_positions 
                SET stop_loss = :stop_loss,
                    take_profit = :take_profit,
                    updated_at = NOW()
                WHERE entry_time = :entry_time
            """), {
                'stop_loss': position['stop_loss'],
                'take_profit': position['take_profit'],
                'entry_time': position['entry_time']
            })
            await session.commit()

    async def delete_position(self) -> None:
        """删除持仓记录"""
        async with self.db_manager.get_session() as session:
            await session.execute(text("DELETE FROM active_positions"))
            await session.commit()

    @async_timer
    async def get_funding_cost_data(self, symbol: str, hours: int = 24) -> List[Dict]:
        """
        获取资金费率数据用于成本计算
        :param symbol: 交易对符号
        :param hours: 时间范围（小时）
        :return: 资金费率记录列表
        """
        async with self.db_manager.get_session() as session:
            try:
                from_time = datetime.now() - timedelta(hours=hours)
                
                result = await session.execute(text("""
                    SELECT 
                        fundingTime,
                        fundingRate,
                        realizedRate,
                        method
                    FROM Fundingrate 
                    WHERE symbol = :symbol 
                        AND fundingTime >= :from_time
                    ORDER BY fundingTime DESC
                """), {
                    'symbol': symbol,
                    'from_time': from_time
                })
                
                funding_records = result.fetchall()
                return [dict(row._mapping) for row in funding_records] if funding_records else []
                
            except Exception as e:
                logging.error(f"获取资金费率数据失败: {e}")
                return []

    @async_timer
    async def get_funding_rate_trend_data(self, symbol: str, days: int = 7) -> List[Dict]:
        """
        获取资金费率趋势数据
        :param symbol: 交易对符号
        :param days: 分析天数
        :return: 趋势数据列表
        """
        async with self.db_manager.get_session() as session:
            try:
                from_time = datetime.now() - timedelta(days=days)
                
                result = await session.execute(text("""
                    SELECT 
                        DATE(fundingTime) as funding_date,
                        AVG(fundingRate) as avg_rate,
                        MIN(fundingRate) as min_rate,
                        MAX(fundingRate) as max_rate,
                        COUNT(*) as periods_count
                    FROM Fundingrate 
                    WHERE symbol = :symbol 
                        AND fundingTime >= :from_time
                    GROUP BY DATE(fundingTime)
                    ORDER BY funding_date DESC
                """), {
                    'symbol': symbol,
                    'from_time': from_time
                })
                
                trend_data = result.fetchall()
                return [dict(row._mapping) for row in trend_data] if trend_data else []
                
            except Exception as e:
                logging.error(f"获取资金费率趋势数据失败: {e}")
                return []

    @async_timer
    async def get_latest_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        获取最新的资金费率
        :param symbol: 交易对符号
        :return: 最新资金费率信息
        """
        async with self.db_manager.get_session() as session:
            try:
                result = await session.execute(text("""
                    SELECT 
                        fundingTime,
                        fundingRate,
                        realizedRate,
                        method
                    FROM Fundingrate 
                    WHERE symbol = :symbol 
                    ORDER BY fundingTime DESC
                    LIMIT 1
                """), {'symbol': symbol})
                
                latest_record = result.fetchone()
                return dict(latest_record._mapping) if latest_record else None
                
            except Exception as e:
                logging.error(f"获取最新资金费率失败: {e}")
                return None