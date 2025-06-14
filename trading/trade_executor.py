from typing import Dict, Optional, Any
import logging
from datetime import datetime
from database.dao import TradeStrategyDAO
from config.settings import Config


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
        
    async def execute_order(self, order_params: Dict) -> Dict:
        """
        执行下单操作
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
            
            self.logger.info(f"下单成功: {order_params}")
            self.logger.info(f"下单结果: {order_result}")
            
            return {
                'success': True,
                'order_result': order_result,
                'order_params': order_params
            }
            
        except Exception as e:
            self.logger.error(f"下单失败: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'order_params': order_params
            }
    
    async def open_position(self, trade_signal: Dict) -> Dict:
        """
        开仓操作
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
            order_result = await self.execute_order(order_params)
            
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
                    'day': trade_signal['day']
                }
                
                await self.dao.save_position(position_data)
                
                self.logger.info(f"开仓成功: {position_data}")
                
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
            self.logger.error(f"开仓操作失败: {str(e)}")
            return {
                'action': 'open_position_failed',
                'success': False,
                'error': str(e)
            }
    
    async def close_position(self, close_signal: Dict) -> Dict:
        """
        平仓操作
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
            order_result = await self.execute_order(order_params)
            
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
                    'exit_reason': close_signal['reason']
                }
                
                # 记录交易结果
                await self.dao.record_trade(trade_result)
                
                # 删除活跃持仓记录
                await self.dao.delete_position()
                
                self.logger.info(f"平仓成功: {trade_result}")
                
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
            self.logger.error(f"平仓操作失败: {str(e)}")
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