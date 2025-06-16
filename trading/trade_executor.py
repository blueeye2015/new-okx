from typing import Dict, Optional, Any
import logging
from datetime import datetime
from database.dao import TradeStrategyDAO
from config.settings import Config
from exchange.base import ExchangeBase


class TradeExecutor:
    """交易执行器 - 负责实际的下单和持仓管理"""
    
    def __init__(self, config: Config, dao: TradeStrategyDAO):
        """
        初始化交易执行器
        :param config: 配置对象
        :param dao: 数据访问对象
        """
        self.config = config
        self.dao = dao
        self.logger = logging.getLogger('TradeExecutor')
        self.exchange_base = ExchangeBase(is_simulated=config.IS_SIMULATED)
        
    async def execute_spot_order(self, order_params: Dict) -> Dict:
        """
        执行现货下单操作
        :param order_params: 下单参数
        :return: 下单结果
        """
        try:
            from trade.place_order import OkexOrderManager
            order_manager = OkexOrderManager(is_simulated=self.config.IS_SIMULATED)
            
            # 执行下单
            order_result = order_manager.place_order(
                instrument_id=order_params['instrument_id'],
                order_type=order_params.get('order_type', 'market'),
                side=order_params['side'],
                price=order_params['price'],
                size=order_params['size']
            )
            
            self.logger.info(f"现货下单成功: {order_params}")
            self.logger.info(f"下单结果: {order_result}")
            
            return {
                'success': True,
                'order_result': order_result,
                'order_params': order_params,
                'order_type': 'spot'
            }
            
        except Exception as e:
            self.logger.error(f"现货下单失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'order_params': order_params,
                'order_type': 'spot'
            }

    async def execute_swap_order(self, order_params: Dict) -> Dict:
        """
        执行合约下单操作
        :param order_params: 下单参数
        :return: 下单结果
        """
        try:
            # 使用 OKX API 下合约单
            from okex.Trade_api import TradeAPI
            
            trade_api = TradeAPI(
                self.exchange_base.api_key,
                self.exchange_base.secret_key,
                self.exchange_base.passphrase,
                False,  # use_server_time
                self.exchange_base.flag,
                proxies=self.exchange_base.proxies
            )
            
            # 构建合约下单参数
            order_data = {
                'instId': order_params['instrument_id'],
                'tdMode': order_params.get('td_mode', 'cross'),  # 交易模式：cross(全仓), isolated(逐仓)
                'side': order_params['side'],  # buy, sell
                'ordType': order_params.get('order_type', 'market'),  # market, limit
                'sz': str(order_params['size']),  # 数量
            }
            
            # 对于净持仓模式，不需要指定posSide
            # 只有在双向持仓模式下才需要指定posSide
            pos_side = order_params.get('pos_side', 'net')
            if pos_side != 'net':
                order_data['posSide'] = pos_side
            
            # 如果是限价单，需要添加价格
            if order_data['ordType'] == 'limit':
                order_data['px'] = str(order_params['price'])
            
            # 执行下单
            order_result = trade_api.place_order(**order_data)
            
            self.logger.info(f"合约下单成功: {order_params}")
            self.logger.info(f"下单结果: {order_result}")
            
            return {
                'success': True,
                'order_result': order_result,
                'order_params': order_params,
                'order_type': 'swap'
            }
            
        except Exception as e:
            self.logger.error(f"合约下单失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'order_params': order_params,
                'order_type': 'swap'
            }

    async def execute_order(self, order_params: Dict) -> Dict:
        """
        执行下单操作（自动判断现货或合约）
        :param order_params: 下单参数
        :return: 下单结果
        """
        # 根据交易对判断是现货还是合约
        instrument_id = order_params['instrument_id']
        if 'SWAP' in instrument_id or 'FUTURES' in instrument_id:
            return await self.execute_swap_order(order_params)
        else:
            return await self.execute_spot_order(order_params)

    async def open_swap_position(self, trade_signal: Dict) -> Dict:
        """
        开合约仓位
        :param trade_signal: 交易信号
        :return: 开仓结果
        """
        try:
            # 准备合约下单参数
            order_params = {
                'instrument_id': trade_signal.get('instrument_id', self.config.TRADING_SYMBOL),
                'order_type': 'market',
                'side': 'buy' if trade_signal['direction'] == 'long' else 'sell',
                'price': trade_signal['entry_price'],
                'size': trade_signal['contract_size'],  # 合约张数
                'td_mode': trade_signal.get('td_mode', 'cross'),
                'pos_side': 'long' if trade_signal['direction'] == 'long' else 'short'
            }
            
            # 执行下单
            order_result = await self.execute_swap_order(order_params)
            
            if order_result['success']:
                # 保存持仓信息到数据库
                position_data = {
                    'direction': trade_signal['direction'],
                    'entry_price': trade_signal['entry_price'],
                    'size': trade_signal['contract_size'],
                    'stop_loss': trade_signal['stop_loss'],
                    'take_profit': trade_signal['take_profit'],
                    'entry_time': datetime.now(),
                    'pattern': trade_signal['pattern'],
                    'day': trade_signal['day'],
                    'instrument_type': 'swap',
                    'td_mode': order_params['td_mode']
                }
                
                await self.dao.save_position(position_data)
                
                self.logger.info(f"合约开仓成功: {position_data}")
                
                return {
                    'action': 'open_swap_position',
                    'success': True,
                    'position': position_data,
                    'order_result': order_result['order_result'],
                    'funding_info': trade_signal.get('funding_info')
                }
            else:
                return {
                    'action': 'open_swap_position_failed',
                    'success': False,
                    'error': order_result['error']
                }
                
        except Exception as e:
            self.logger.error(f"合约开仓操作失败: {str(e)}")
            return {
                'action': 'open_swap_position_failed',
                'success': False,
                'error': str(e)
            }

    async def close_swap_position(self, close_signal: Dict) -> Dict:
        """
        平合约仓位
        :param close_signal: 平仓信号
        :return: 平仓结果
        """
        try:
            # 获取当前持仓
            position = await self.dao.get_active_position()
            
            if not position:
                return {
                    'action': 'close_swap_position_failed',
                    'success': False,
                    'error': 'no_active_position'
                }
            
            # 准备平仓订单参数
            order_params = {
                'instrument_id': close_signal.get('instrument_id', self.config.TRADING_SYMBOL),
                'order_type': 'market',
                'side': 'sell' if position['direction'] == 'long' else 'buy',
                'price': close_signal['exit_price'],
                'size': position['size'],  # 合约张数
                'td_mode': position.get('td_mode', 'cross'),
                'pos_side': 'long' if position['direction'] == 'long' else 'short'
            }
            
            # 执行平仓
            order_result = await self.execute_swap_order(order_params)
            
            if order_result['success']:
                # 计算交易结果
                if position['direction'] == 'long':
                    profit_per_contract = close_signal['exit_price'] - position['entry_price']
                else:
                    profit_per_contract = position['entry_price'] - close_signal['exit_price']
                
                total_profit = profit_per_contract * position['size']
                profit_pct = profit_per_contract / position['entry_price']
                
                trade_result = {
                    'entry_time': position['entry_time'],
                    'exit_time': datetime.now(),
                    'entry_price': position['entry_price'],
                    'exit_price': close_signal['exit_price'],
                    'profit_pct': profit_pct,
                    'profit_amount': total_profit,
                    'day_of_week': position['day'],
                    'pattern_type': position['pattern'],
                    'exit_reason': close_signal['reason'],
                    'instrument_type': 'swap',
                    'contract_size': position['size']
                }
                
                # 记录交易结果
                await self.dao.record_trade(trade_result)
                
                # 删除活跃持仓记录
                await self.dao.delete_position()
                
                self.logger.info(f"合约平仓成功: {trade_result}")
                
                return {
                    'action': 'close_swap_position',
                    'success': True,
                    'trade_result': trade_result,
                    'order_result': order_result['order_result']
                }
            else:
                return {
                    'action': 'close_swap_position_failed',
                    'success': False,
                    'error': order_result['error']
                }
                
        except Exception as e:
            self.logger.error(f"合约平仓操作失败: {str(e)}")
            return {
                'action': 'close_swap_position_failed',
                'success': False,
                'error': str(e)
            }

    async def get_swap_positions(self) -> Dict:
        """
        获取合约持仓信息
        :return: 持仓信息
        """
        try:
            positions = self.exchange_base.get_positions(instrument_type='SWAP')
            self.logger.info(f"获取合约持仓成功: {positions}")
            return {
                'success': True,
                'positions': positions
            }
        except Exception as e:
            self.logger.error(f"获取合约持仓失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    # 保留原有的现货交易方法
    async def open_position(self, trade_signal: Dict) -> Dict:
        """
        开仓操作（现货）
        :param trade_signal: 交易信号
        :return: 开仓结果
        """
        try:
            # 准备下单参数
            order_params = {
                'instrument_id': self.config.TRADING_SYMBOL,
                'order_type': 'market',
                'side': 'buy' if trade_signal['direction'] == 'long' else 'sell',
                'price': trade_signal['entry_price'],
                'size': trade_signal['btc_amount']
            }
            
            # 执行下单
            order_result = await self.execute_spot_order(order_params)
            
            if order_result['success']:
                # 保存持仓信息到数据库
                position_data = {
                    'direction': trade_signal['direction'],
                    'entry_price': trade_signal['entry_price'],
                    'size': trade_signal['trade_amount'],
                    'stop_loss': trade_signal['stop_loss'],
                    'take_profit': trade_signal['take_profit'],
                    'entry_time': datetime.now(),
                    'pattern': trade_signal['pattern'],
                    'day': trade_signal['day'],
                    'instrument_type': 'spot'
                }
                
                await self.dao.save_position(position_data)
                
                self.logger.info(f"现货开仓成功: {position_data}")
                
                return {
                    'action': 'open_position',
                    'success': True,
                    'position': position_data,
                    'order_result': order_result['order_result'],
                    'funding_info': trade_signal.get('funding_info')
                }
            else:
                return {
                    'action': 'open_position_failed',
                    'success': False,
                    'error': order_result['error']
                }
                
        except Exception as e:
            self.logger.error(f"现货开仓操作失败: {str(e)}")
            return {
                'action': 'open_position_failed',
                'success': False,
                'error': str(e)
            }

    # 保留其他原有方法...
    async def close_position(self, close_signal: Dict) -> Dict:
        """
        平仓操作（现货）
        :param close_signal: 平仓信号
        :return: 平仓结果
        """
        try:
            # 获取当前持仓
            position = await self.dao.get_active_position()
            
            if not position:
                return {
                    'action': 'close_position_failed',
                    'success': False,
                    'error': 'no_active_position'
                }
            
            # 计算平仓数量
            btc_amount = position['size'] / position['entry_price']
            
            # 准备平仓订单参数
            order_params = {
                'instrument_id': self.config.TRADING_SYMBOL,
                'order_type': 'market',
                'side': 'sell' if position['direction'] == 'long' else 'buy',
                'price': close_signal['exit_price'],
                'size': btc_amount
            }
            
            # 执行平仓
            order_result = await self.execute_spot_order(order_params)
            
            if order_result['success']:
                # 计算交易结果
                profit = (close_signal['exit_price'] - position['entry_price']) * \
                        (1 if position['direction'] == 'long' else -1)
                profit_pct = profit / position['entry_price']
                
                trade_result = {
                    'entry_time': position['entry_time'],
                    'exit_time': datetime.now(),
                    'entry_price': position['entry_price'],
                    'exit_price': close_signal['exit_price'],
                    'profit_pct': profit_pct,
                    'profit_amount': profit * position['size'],
                    'day_of_week': position['day'],
                    'pattern_type': position['pattern'],
                    'exit_reason': close_signal['reason'],
                    'instrument_type': 'spot'
                }
                
                # 记录交易结果
                await self.dao.record_trade(trade_result)
                
                # 删除活跃持仓记录
                await self.dao.delete_position()
                
                self.logger.info(f"现货平仓成功: {trade_result}")
                
                return {
                    'action': 'close_position',
                    'success': True,
                    'trade_result': trade_result,
                    'order_result': order_result['order_result']
                }
            else:
                return {
                    'action': 'close_position_failed',
                    'success': False,
                    'error': order_result['error']
                }
                
        except Exception as e:
            self.logger.error(f"现货平仓操作失败: {str(e)}")
            return {
                'action': 'close_position_failed',
                'success': False,
                'error': str(e)
            }

    async def update_position_stops(self, position: Dict, new_stop_loss: float, new_take_profit: float) -> Dict:
        """
        更新持仓的止损止盈
        :param position: 持仓信息
        :param new_stop_loss: 新的止损价格
        :param new_take_profit: 新的止盈价格
        :return: 更新结果
        """
        try:
            updated_position = position.copy()
            updated_position['stop_loss'] = new_stop_loss
            updated_position['take_profit'] = new_take_profit
            
            await self.dao.update_position(updated_position)
            
            self.logger.info(f"更新持仓止损止盈: 止损 {new_stop_loss}, 止盈 {new_take_profit}")
            
            return {
                'action': 'update_stops',
                'success': True,
                'position': updated_position
            }
            
        except Exception as e:
            self.logger.error(f"更新持仓止损止盈失败: {str(e)}")
            return {
                'action': 'update_stops_failed',
                'success': False,
                'error': str(e)
            }
    
    async def get_current_position(self) -> Optional[Dict]:
        """
        获取当前持仓
        :return: 持仓信息
        """
        try:
            return await self.dao.get_active_position()
        except Exception as e:
            self.logger.error(f"获取当前持仓失败: {str(e)}")
            return None
    
    async def calculate_position_pnl(self, current_price: float) -> Optional[Dict]:
        """
        计算当前持仓的盈亏
        :param current_price: 当前价格
        :return: 盈亏信息
        """
        try:
            position = await self.get_current_position()
            
            if not position:
                return None
            
            # 计算盈亏
            if position['direction'] == 'long':
                unrealized_pnl = (current_price - position['entry_price']) * position['size'] / position['entry_price']
            else:
                unrealized_pnl = (position['entry_price'] - current_price) * position['size'] / position['entry_price']
            
            pnl_pct = unrealized_pnl / position['size'] * 100
            
            pnl_info = {
                'position': position,
                'current_price': current_price,
                'unrealized_pnl': round(unrealized_pnl, 6),
                'pnl_percentage': round(pnl_pct, 4),
                'entry_price': position['entry_price'],
                'position_size': position['size']
            }
            
            return pnl_info
            
        except Exception as e:
            self.logger.error(f"计算持仓盈亏失败: {str(e)}")
            return None 