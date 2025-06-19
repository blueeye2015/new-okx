import pandas as pd
import requests
import psycopg2
from datetime import datetime, timedelta
import time

def get_binance_klines(symbol, interval, start_time, end_time=None):
    """
    从 Binance API 获取 K 线数据
    """
    endpoint = "https://api.binance.com/api/v3/klines"
    
    if end_time is None:
        end_time = int(datetime.now().timestamp() * 1000)
        
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': start_time,
        'endTime': end_time,
        'limit': 1000  # Binance 每次最多返回1000条数据
    }
    
    response = requests.get(endpoint, params=params)
    return response.json()

# 这里展示修改后的函数
def get_crypto_data_hourly():
    """
    获取比特币小时级历史数据
    """
    try:
        print("正在从 Binance 获取小时级数据...")
        
        # 设置时间范围 - 建议缩短时间范围，因为小时数据量很大
        start_date = datetime(2020, 1, 1)  # 从2020年开始，避免数据量过大
        end_date = datetime.now()
        
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        all_klines = []
        current_start = start_ts
        
        # 分批获取数据
        while current_start < end_ts:
            print(f"获取从 {datetime.fromtimestamp(current_start/1000)} 开始的数据...")
            
            # 每次获取约40天的小时数据（约1000条记录）
            batch_end = min(current_start + 40 * 24 * 60 * 60 * 1000, end_ts)
            
            klines = get_binance_klines(
                symbol='BTCUSDT',
                interval='1h',  # 小时级数据
                start_time=current_start,
                end_time=batch_end
            )
            
            if not klines:
                break
                
            all_klines.extend(klines)
            
            # 更新起始时间 - 基于最后一条记录的时间
            current_start = klines[-1][0] + 60 * 60 * 1000  # 下一小时
            
            # 添加延时以避免触发API限制
            time.sleep(0.2)  # 稍微增加延时
        
        # 后续处理代码保持不变...
        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 
            'volume', 'close_time', 'quote_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        # 转换数据类型
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        # 重命名和选择所需的列
        df = df.rename(columns={'timestamp': 'date'})
        df['adj_close'] = df['close']
        df = df[['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']]
        df = df.sort_values('date')
        
        print(f"成功获取了 {len(df)} 条小时级数据记录")
        print("\n数据样本:")
        print(df.head())
        
        return df
        
    except Exception as e:
        print(f"获取数据时出错: {e}")
        return None

print("小时级数据获取函数已定义完成")


def create_database_connection():
    """
    创建数据库连接
    """
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="market_data",
            user="postgres",
            password="12"
        )
        return conn
    
    except Exception as e:
        print(f"数据库连接错误: {e}")
        return None

def create_crypto_table(conn):
    """
    创建加密货币数据表
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS crypto_prices_hourly (
    id SERIAL PRIMARY KEY,
    trade_date TIMESTAMP NOT NULL,  -- 改为TIMESTAMP以包含小时信息
    open FLOAT NOT NULL,
    high FLOAT NOT NULL,
    low FLOAT NOT NULL,
    close FLOAT NOT NULL,
    adj_close FLOAT NOT NULL,
    volume FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(create_table_query)
        conn.commit()
        print("表创建成功")
    except Exception as e:
        print(f"创建表时出错: {e}")
        conn.rollback()

def save_to_database(df, conn):
    """
    将数据保存到数据库
    """
    try:
        # 准备插入语句
        insert_query = """
        INSERT INTO crypto_prices_hourly (trade_date , open, high, low, close, adj_close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        # 准备数据
        data = [tuple(x) for x in df.values]
        
        # 使用cursor执行插入
        with conn.cursor() as cur:
            cur.executemany(insert_query, data)
        
        conn.commit()
        print("数据已成功保存到数据库")
    
    except Exception as e:
        print(f"保存数据时出错: {e}")
        conn.rollback()

def verify_data(conn):
    """
    验证保存的数据
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM crypto_prices")
            count = cur.fetchone()[0]
            print(f"数据库中共有 {count} 条记录")
            
            # 显示一些样本数据
            cur.execute("""
                SELECT trade_date, 
                       round(open::numeric, 2) as open,
                       round(close::numeric, 2) as close,
                       round(volume::numeric, 2) as volume
                FROM crypto_prices 
                ORDER BY trade_date DESC 
                LIMIT 5
            """)
            recent_data = cur.fetchall()
            print("\n最近5条记录:")
            for row in recent_data:
                print(row)
                
    except Exception as e:
        print(f"验证数据时出错: {e}")

def main():
    try:
        # 获取数据
        df = get_crypto_data_hourly()
        
        if df is None or df.empty:
            print("未能获取数据，程序终止")
            return
            
        # 创建数据库连接
        print("正在连接数据库...")
        conn = create_database_connection()
        
        if conn is not None:
            try:
                # 创建表
                create_crypto_table(conn)
                
                # 保存数据
                save_to_database(df, conn)
                
                # 验证数据
                verify_data(conn)
                
            finally:
                conn.close()
                print("数据库连接已关闭")
    
    except Exception as e:
        print(f"程序执行出错: {e}")

if __name__ == "__main__":
    main()
