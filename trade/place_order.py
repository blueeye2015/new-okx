import okex.Account_api as Account
import json
from trade.api_parser import parse_positions, parse_orderlist, parse_balance
import logging
from trade.regular_err import SpecialJumpException
from exchange.base import ExchangeBase
import okex.Trade_api as Trade

class OkexOrderManager(ExchangeBase):
    def __init__(self, is_simulated=False):
        
        """
        使用代理设置初始化订单处理程序。

        参数：
            proxy_host (str): 代理服务器的主机地址，默认为 "127.0.0.1"。
            proxy_port (str): 代理服务器的端口号，默认为 "7890"。
        """

        super().__init__()
        self.flag = '0' if is_simulated==False else '1' 
        
        # 初始化API
        self.init_api()
        
        # 设置日志
        #self.setup_logging()
        
    def init_api(self):
        """初始化API连接"""
        try:
            self.tradeAPI = Trade.TradeAPI(
                self.api_key,
                self.secret_key,
                self.passphrase,
                False,
                self.flag,
                self.proxies
            )
        except Exception as e:
            self.logger.error(f"API初始化失败: {str(e)}")
            raise
    
    # def setup_logging(self):
    #     """设置日志配置"""
    #     logging.basicConfig(
    #         filename='place_order.log',
    #         level=logging.INFO,
    #         format='%(asctime)s - %(levelname)s - %(message)s'
    #     )
    #     self.logger = logging.getLogger(__name__)
        self.logger.info('OkexAccountManager initialized')
            
    def place_order(self, instrument_id, order_type, side, price, size):
            # 实现下单逻辑
            try:
                order_data = {
                    "instId": instrument_id,
                    "tdMode": "cross",
                    "side": side,
                    "ordType": order_type,
                    "px": str(price),
                    "sz": str(size)
                }
                result = self.tradeAPI.place_order(**order_data)
                return result
            except Exception as e:
                raise e