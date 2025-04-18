import logging
from time import sleep
from datetime import datetime
from config.settings import Config
from database.manager import DatabaseManager
from services.market_data import MarketDataService
import asyncio



async def main():
    logging.basicConfig(filename='klines.log', 
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    config = Config()
    db_manager = DatabaseManager(config.DB_CONFIG)
    market_service = MarketDataService(config)
  
    while True:
        try:
            
            config.update_symbols()
            
            await market_service.run()
            
        except KeyboardInterrupt:
            logging.info("程序正在退出...")
            await db_manager.close()
            break
        except Exception as e:
            logging.error(f"发生错误: {str(e)}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
