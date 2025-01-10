import ccxt
import logging
from dotenv import load_dotenv
import os
import okex.Public_api as Public

class ExchangeBase:
    _instance = None
    _exchange = None
    _public_api = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ExchangeBase, cls).__new__(cls)
        return cls._instance
    
    @property
    def exchange(self) -> ccxt.Exchange:
        if self._exchange is None:
            load_dotenv('D:\OKex-API\.env')
            self.api_key = os.getenv('API_KEY')
            self.secret_key = os.getenv('SECRET_KEY')
            self.passphrase = os.getenv('PASSPHRASE')
            self.proxies = {
                'http': 'http://127.0.0.1:7890',
                'https': 'http://127.0.0.1:7890'
            }
            self._exchange = self._create_exchange()
        return self._exchange
    
    @property
    def public_api(self):
        if self._public_api is None:
            # 确保credentials已经加载
            if not hasattr(self, 'api_key'):
                load_dotenv('D:\OKex-API\.env')
                self.api_key = os.getenv('API_KEY')
                self.secret_key = os.getenv('SECRET_KEY')
                self.passphrase = os.getenv('PASSPHRASE')
                self.proxies = {
                    'http': 'http://127.0.0.1:7890',
                    'https': 'http://127.0.0.1:7890'
                }
            self._public_api = self._create_public_api()
        return self._public_api
    
    def _create_exchange(self):
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
            }
        })
    
    def _create_public_api(self):
        flag = '0'  # 0: 生产环境，1: 模拟盘
        return Public.PublicAPI(
            self.api_key, 
            self.secret_key, 
            self.passphrase, 
            False,  # use_server_time
            flag,
            proxies=self.proxies
        )
