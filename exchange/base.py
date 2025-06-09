import ccxt
import logging
from dotenv import load_dotenv
import os
import okex.Public_api as Public
import okex.Account_api as Account
import json
from typing import Dict, Any, Optional

class ExchangeBase:
    _instance = None
    _exchange = None
    _public_api = None
    _account_api = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ExchangeBase, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, is_simulated: bool = False):
        """
        初始化交易所基类
        
        Args:
            is_simulated (bool): 是否使用模拟盘，默认False表示实盘
        """
        # 设置是否为模拟盘
        self.flag = '1' if is_simulated else '0'
        self._setup_base_logging()
        
        # 初始化时就加载市场数据
        if not hasattr(self, '_markets_loaded'):
            self._load_credentials()
            self._initialize_exchange()
            self._markets_loaded = True
    
    def _load_credentials(self):
        """加载API凭证"""
        if not hasattr(self, 'api_key'):
            load_dotenv('D:\OKex-API\.env')
            self.api_key = os.getenv('API_KEY')
            self.secret_key = os.getenv('SECRET_KEY')
            self.passphrase = os.getenv('PASSPHRASE')
            self.proxies = {
                'http': 'http://127.0.0.1:7890',
                'https': 'http://127.0.0.1:7890'
            }
    
    def _initialize_exchange(self):
        """初始化交易所连接并加载市场数据"""
        try:
            self._exchange = self._create_exchange()
            self._exchange.load_markets()
            self.logger.info("交易所市场数据加载成功")
        except Exception as e:
            self.logger.error(f"交易所市场数据加载失败: {str(e)}")
            raise
    
    @property
    def exchange(self) -> ccxt.Exchange:
        if self._exchange is None:
            self._load_credentials()
            self._initialize_exchange()
        return self._exchange
    
    @property
    def public_api(self):
        if self._public_api is None:
            self._load_credentials()
            self._public_api = self._create_public_api()
        return self._public_api
    
    @property
    def account_api(self):
        if self._account_api is None:
            self._load_credentials()
            self._account_api = self._create_account_api()
        return self._account_api
    
    def _create_exchange(self):
        """创建 CCXT exchange 实例"""
        return ccxt.okx({
            'apiKey': self.api_key,
            'secret': self.secret_key,
            'password': self.passphrase,
            'enableRateLimit': True,
            'proxies': self.proxies,
            'timeout': 30000,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True
            },
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
            }
        })

    def convert_symbol_format(self, symbol: str, to_exchange: bool = True) -> str:
        """
        转换交易对格式
        
        Args:
            symbol (str): 交易对
            to_exchange (bool): True 转换为交易所格式 (BTC-USDT)，False 转换为标准格式 (BTC/USDT)
            
        Returns:
            str: 转换后的交易对格式
        """
        if to_exchange:
            return symbol.replace('/', '-')
        return symbol.replace('-', '/')

    def fetch_ticker(self, symbol: str):
        """
        获取交易对的ticker数据
        
        Args:
            symbol (str): 交易对（可以是 BTC/USDT 或 BTC-USDT 格式）
            
        Returns:
            dict: ticker数据
        """
        try:
            # 确保使用交易所要求的格式
            exchange_symbol = self.convert_symbol_format(symbol, to_exchange=True)
            return self.exchange.fetch_ticker(exchange_symbol)
        except Exception as e:
            self.logger.error(f"获取ticker数据失败: {str(e)}")
            raise

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', since: int = None, limit: int = None):
        """
        获取K线数据
        
        Args:
            symbol (str): 交易对（可以是 BTC/USDT 或 BTC-USDT 格式）
            timeframe (str): 时间周期
            since (int): 开始时间戳（毫秒）
            limit (int): 返回记录数量
            
        Returns:
            list: K线数据列表
        """
        try:
            # 确保使用交易所要求的格式
            exchange_symbol = self.convert_symbol_format(symbol, to_exchange=True)
            return self.exchange.fetch_ohlcv(exchange_symbol, timeframe, since, limit)
        except Exception as e:
            self.logger.error(f"获取K线数据失败: {str(e)}")
            raise

    def _create_public_api(self):
        return Public.PublicAPI(
            self.api_key, 
            self.secret_key, 
            self.passphrase, 
            False,  # use_server_time
            self.flag,
            proxies=self.proxies
        )
    
    def _create_account_api(self):
        return Account.AccountAPI(
            self.api_key,
            self.secret_key,
            self.passphrase,
            False,  # use_server_time
            self.flag,
            proxies=self.proxies
        )

    def get_positions(self, instrument_type: str = 'SWAP', instrument_id: str = '') -> Dict[str, Any]:
        """
        获取持仓信息
        
        Args:
            instrument_type (str): 产品类型，默认'SWAP'
            instrument_id (str): 产品ID，默认为空
            
        Returns:
            dict: 解析后的持仓信息
        """
        try:
            result = self.account_api.get_positions(instrument_type, instrument_id)
            self.logger.info("Successfully retrieved positions")
            return result
        except Exception as e:
            self.logger.error(f"获取持仓信息失败: {str(e)}")
            raise

    def get_balance(self, currency: str = 'USDT') -> float:
        """
        获取保证金余额
        
        Args:
            currency (str): 货币类型，默认'USDT'
            
        Returns:
            float: 解析后的余额信息
        """
        try:
            result = self.account_api.get_account(currency)
            # 解析余额信息
            if isinstance(result, dict) and 'data' in result:
                for item in result['data'][0]['details']:
                    if item['ccy'] == currency:
                        balance = float(item['cashBal'])
                        self.logger.info(f"Successfully retrieved balance for {currency}: {balance}")
                        return balance
            raise ValueError(f"Unable to find balance for {currency}")
        except Exception as e:
            self.logger.error(f"获取余额失败: {str(e)}")
            raise

    def get_account_info(self) -> Dict[str, Any]:
        """
        获取账户完整信息（包括持仓和余额）
        
        Returns:
            dict: 包含持仓和余额信息的字典
        """
        try:
            positions = self.get_positions()
            balance = self.get_balance()
            
            return {
                'positions': positions,
                'balance': balance
            }
        except Exception as e:
            self.logger.error(f"获取账户信息失败: {str(e)}")
            raise

    def _setup_base_logging(self):
        """设置基本的日志配置"""
        logging.basicConfig(
            filename='exchange_base.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f'{self.__class__.__name__} initialized')