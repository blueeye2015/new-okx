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
    INTERVAL = "1m"
    BATCH_SIZE = 10
    SYMBOLS = []  # 将由market_analyzer更新
    SYMBOLS_SWAP = [] # 所有合约
    INITIAL_CAPITAL =  100 #默认初始资金
    IS_SIMULATED = False  # 是否使用模拟盘，默认使用实盘
    TRADING_SYMBOL = 'BTC-USDT'  # 交易对

    def __init__(self):
        from services.market_analyzer import MarketAnalyzer
        self.market_analyzer = MarketAnalyzer()
        self.update_symbols()
    
    def update_symbols(self):
        #self.SYMBOLS = self.market_analyzer.get_valid_symbols()
        self.SYMBOLS = ['BTC-USDT']
        #self.SYMBOLS_SWAP = self.market_analyzer.get_valid_swap() 
