import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase
import enum
from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean, Numeric
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class KlineModel(Base):
    __tablename__ = 'kline_data'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20))
    timestamp = Column(DateTime(timezone=True))
    open_price = Column(Numeric(20, 8))
    high_price = Column(Numeric(20, 8))
    low_price = Column(Numeric(20, 8))
    close_price = Column(Numeric(20, 8))
    volume = Column(Numeric(20, 8))
    volume_currency = Column(Numeric(20, 8))
    volume_currency_quote = Column(Numeric(20, 8))
    is_confirmed = Column(Boolean)
    created_at = Column(DateTime(timezone=True), server_default='CURRENT_TIMESTAMP')


class TradeModel(Base):
    __tablename__ = 'trade_data'
    
    symbol = sa.Column(sa.String, primary_key=True)
    timestamp = sa.Column(sa.DateTime, primary_key=True)
    tradeId = sa.Column(sa.String)
    px = sa.Column(sa.Float)
    sz = sa.Column(sa.Float)
    side = sa.Column(sa.String)

class FundingRateModel(Base):
    __tablename__ = 'FundingRate'    
    
    symbol = sa.Column(sa.String, primary_key=True)
    fundingTime = sa.Column(sa.DateTime, primary_key=True)
    fundingRate = sa.Column(sa.Float)
    realizedRate = sa.Column(sa.Float)
    method = sa.Column(sa.String)
    
     