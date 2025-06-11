import ccxt
import logging
from dotenv import load_dotenv
import os
import okex.Public_api as Public
import okex.Account_api as Account
import okex.Market_api as Market
import json
from typing import Dict, Any, Optional
from datetime import datetime

class ExchangeBase:
    _instance = None
    _exchange = None
    _public_api = None
    _account_api = None
    _market_api = None
    
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
        
        # 初始化时就加载API
        if not hasattr(self, '_apis_loaded'):
            self._load_credentials()
            self._initialize_apis()
            self._apis_loaded = True
    
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
    
    def _initialize_apis(self):
        """初始化所有API"""
        try:
            self._public_api = self._create_public_api()
            self._account_api = self._create_account_api()
            self._market_api = self._create_market_api()
            self.logger.info("所有API初始化成功")
        except Exception as e:
            self.logger.error(f"API初始化失败: {str(e)}")
            raise
    
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

    @property
    def market_api(self):
        if self._market_api is None:
            self._load_credentials()
            self._market_api = self._create_market_api()
        return self._market_api
    
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

    def _create_market_api(self):
        return Market.MarketAPI(
            self.api_key,
            self.secret_key,
            self.passphrase,
            False,  # use_server_time
            self.flag,
            proxies=self.proxies
        )

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取交易对的ticker数据
        
        Args:
            symbol (str): 交易对，例如 "BTC-USDT"
            
        Returns:
            dict: ticker数据
        """
        try:
            result = self.market_api.get_ticker(instId=symbol)
            self.logger.info(f"Successfully retrieved ticker for {symbol}")
            return result
        except Exception as e:
            self.logger.error(f"获取ticker数据失败: {str(e)}")
            raise

    def get_candlesticks(self, symbol: str, bar: str = '1D', limit: int = 100) -> Dict[str, Any]:
        """
        获取K线数据
        
        Args:
            symbol (str): 交易对，例如 "BTC-USDT"
            bar (str): K线周期，默认'1D'
            limit (int): 获取条数，默认100
            
        Returns:
            dict: K线数据
        """
        try:
            result = self.market_api.get_candlesticks(
                instId=symbol,
                bar=bar,
                limit=str(limit)
            )
            self.logger.info(f"Successfully retrieved candlesticks for {symbol}")
            return result
        except Exception as e:
            self.logger.error(f"获取K线数据失败: {str(e)}")
            raise

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