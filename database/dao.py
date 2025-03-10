from abc import ABC, abstractmethod
from typing import List, Optional
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