import pandas as pd
import yfinance as yf
import psycopg2
from datetime import datetime

def get_crypto_data():
    """
    从 Yahoo Finance 获取比特币历史数据
    """
    try:
        print("正在从 Yahoo Finance 获取数据...")
        
        # 使用 BTC-USD 符号获取比特币数据
        btc = yf.Ticker("BTC-USD")
        
        # 获取所有可用的历史数据
        df = btc.history(period="max")
        
        # 重置索引，将日期变成列
        df = df.reset_index()
        
        # 重命名列
        df = df.rename(columns={
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        # 添加 adj_close 列（对于加密货币，与 close 相同）
        df['adj_close'] = df['close']
        
        # 选择需要的列
        df = df[['date', 'open', 'high', 'low', 'close', 'adj_close', 'volume']]
        
        print(f"成功获取了 {len(df)} 条数据记录")
        print("\n数据样本:")
        print(df.head())
        
        return df
        
    except Exception as e:
        print(f"获取数据时出错: {e}")
        return None

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
    CREATE TABLE IF NOT EXISTS crypto_prices (
        id SERIAL PRIMARY KEY,
        trade_date DATE NOT NULL,
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
            # 先删除旧表（如果存在）
            cur.execute("DROP TABLE IF EXISTS crypto_prices;")
            # 创建新表
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
        # 重命名 DataFrame 中的 date 列为 trade_date
        df = df.rename(columns={'date': 'trade_date'})
        
        # 准备插入语句
        insert_query = """
        INSERT INTO crypto_prices (trade_date, open, high, low, close, adj_close, volume)
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
            
            # 显示最早的5条记录
            print("\n最早的5条记录:")
            cur.execute("""
                SELECT trade_date, 
                       round(open::numeric, 2) as open,
                       round(close::numeric, 2) as close,
                       round(volume::numeric, 2) as volume
                FROM crypto_prices 
                ORDER BY trade_date ASC
                LIMIT 5
            """)
            earliest_data = cur.fetchall()
            for row in earliest_data:
                print(row)
            
            # 显示最近的5条记录
            print("\n最近的5条记录:")
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
            for row in recent_data:
                print(row)
                
    except Exception as e:
        print(f"验证数据时出错: {e}")

def main():
    try:
        # 获取数据
        df = get_crypto_data()
        
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
