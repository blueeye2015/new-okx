from dataclasses import dataclass

@dataclass
class DBConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

class Config:
    DB_CONFIG = DBConfig(
        host="localhost",
        port=5432,
        database="market_data",
        user="postgres",
        password="12"
    )
    INTERVAL = "1d"
    BATCH_SIZE = 10
    SYMBOLS = []  # 将由market_analyzer更新
    SYMBOLS_SWAP = [] # 所有合约

    def __init__(self):
        from services.market_analyzer import MarketAnalyzer
        self.market_analyzer = MarketAnalyzer()
        self.update_symbols()
    
    def update_symbols(self):
        #self.SYMBOLS = self.market_analyzer.get_valid_symbols()
        self.SYMBOLS = ['BTC-USDT']
        #self.SYMBOLS_SWAP = self.market_analyzer.get_valid_swap() 
