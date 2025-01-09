from dataclasses import dataclass
from datetime import datetime

@dataclass
class Fundingrate:
    """K线数据类"""
    symbol: str
    fundingTime: datetime
    fundingRate: float
    realizedRate: float
    method: str
        
    @classmethod
    def from_exchange_data(cls, symbol: str, data: list) -> 'Fundingrate':
        """
        从交易所数据创建Kline对象
        data格式: [timestamp, open, high, low, close, volume]
        """
        return cls(
            symbol=symbol,
            fundingTime=datetime.fromtimestamp(data[4] / 1000),  # 转换毫秒时间戳
            fundingRate=float(data[2]),
            realizedRate=float(data[3]),
            method=float(data[5])
        )
        
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            'symbol': self.symbol,
            'fundingTime': self.fundingTime,
            'fundingRate': self.fundingRate,
            'realizedRate': self.realizedRate,
            'method': self.method
        }