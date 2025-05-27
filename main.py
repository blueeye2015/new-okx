import logging
from time import sleep
from datetime import datetime
from config.settings import Config
from database.manager import DatabaseManager
from services.market_data import MarketDataService
from services.trade_strategy import BitcoinTradingSystem
import asyncio
import argparse


async def main():
    logging.basicConfig(filename='klines.log', 
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    config = Config()
    db_manager = DatabaseManager(config.DB_CONFIG)
    
    
    
    parser = argparse.ArgumentParser(description='Run market or trade service')
    parser.add_argument('--service', choices=['market', 'trade'], default='market', help='Service to run (market, trade)')
    args = parser.parse_args()
    while True:
        try:
            
            config.update_symbols()
            if args.service == 'market':
                market_service = MarketDataService(config)
                await market_service.run()
            elif args.service == 'trade':
                trade_service = BitcoinTradingSystem(config)
                await trade_service.run()
            #await market_service.run()
            #await trade_service.run()
            
        except KeyboardInterrupt:
            logging.info("程序正在退出...")
            await db_manager.close()
            break
        except Exception as e:
            logging.error(f"发生错误: {str(e)}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
