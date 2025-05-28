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
                    'open': model.open,
                    'high': model.high,
                    'low': model.low,
                    'close': model.close,
                    'volume': model.volume
                } for model in kline_models]
                
                await session.execute(
                    text("""
                    INSERT INTO klines (symbol, timestamp, open, high, low, close, volume)
                    VALUES (:symbol, :timestamp, :open, :high, :low, :close, :volume)
                    ON CONFLICT (symbol, timestamp) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume
                    """),
                    values
                )
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
    
    #@async_timer
    async def get_latest_kline(self, symbol: str) -> Optional[Kline]:
        """获取指定交易对的最新K线数据（同步方式）"""
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
                        open=row.open,
                        high=row.high,
                        low=row.low,
                        close=row.close,
                        volume=row.volume
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
        """创建交易策略相关的表"""
        async with self.db_manager.get_session() as session:
            try:
                # 创建交易历史表
                await session.execute(text("""
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
                """))
                
                # 创建价格模式统计表
                await session.execute(text("""
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
                """))
                
                # 创建索引以提高查询性能
                await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_trade_history_entry_time ON trade_history(entry_time);
                CREATE INDEX IF NOT EXISTS idx_price_patterns_day_pattern ON price_patterns(day_of_week, pattern_type);
                """))
                
                # 创建价格模式统计函数
                await session.execute(text("""
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
                """))
                
                await session.commit()
                logging.info("交易策略相关表创建成功")
            except Exception as e:
                await session.rollback()
                logging.error(f"创建交易策略相关表失败: {e}")
                raise e
    
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