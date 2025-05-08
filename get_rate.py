import pandas as pd
import yfinance as yf
from pandas_datareader import data as pdr
import datetime
import matplotlib.pyplot as plt
import seaborn as sns

def get_treasury_yields(start_date, end_date):
    """
    获取美国国债收益率数据
    DGS10: 10年期国债收益率
    DGS2: 2年期国债收益率
    """
    try:
        treasury_10y = pdr.get_data_fred('DGS10', start_date, end_date)
        treasury_2y = pdr.get_data_fred('DGS2', start_date, end_date)
        
        treasury_data = pd.DataFrame({
            '10Y_YIELD': treasury_10y,
            '2Y_YIELD': treasury_2y
        })
        return treasury_data
    except Exception as e:
        print(f"获取国债收益率数据时出错: {e}")
        return None

def get_fx_rate(start_date, end_date):
    """
    获取USD/JPY汇率数据
    """
    try:
        usdjpy = yf.download('USDJPY=X', start=start_date, end=end_date)
        return usdjpy[['Close']].rename(columns={'Close': 'USDJPY'})
    except Exception as e:
        print(f"获取汇率数据时出错: {e}")
        return None

def get_jpy_rate(start_date, end_date):
    """
    获取日本短期利率数据
    IRSTJPN01STM156N: 日本1个月利率
    """
    try:
        jpy_rate = pdr.get_data_fred('IRSTJPN01STM156N', start_date, end_date)
        return jpy_rate.rename(columns={'IRSTJPN01STM156N': 'JPY_RATE'})
    except Exception as e:
        print(f"获取日本利率数据时出错: {e}")
        return None

def calculate_carry_trade(data):
    """
    计算carry trade收益
    """
    # 计算日收益率
    data['FX_RETURN'] = data['USDJPY'].pct_change()
    
    # 将年化利率转换为日利率
    data['RATE_DIFF'] = (data['2Y_YIELD'] - data['JPY_RATE']) / 252
    
    # 计算总收益
    data['CARRY_RETURN'] = data['RATE_DIFF'] + data['FX_RETURN']
    
    return data

def plot_results(data):
    """
    绘制结果图表
    """
    plt.figure(figsize=(15, 10))
    
    # 创建子图
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12))
    
    # 绘制汇率走势
    data['USDJPY'].plot(ax=ax1, title='USD/JPY Exchange Rate')
    ax1.set_ylabel('Exchange Rate')
    
    # 绘制利率差
    data[['2Y_YIELD', 'JPY_RATE']].plot(ax=ax2, title='Interest Rates')
    ax2.set_ylabel('Rate (%)')
    
    # 绘制累计收益
    cumulative_return = (1 + data['CARRY_RETURN']).cumprod()
    cumulative_return.plot(ax=ax3, title='Cumulative Carry Trade Return')
    ax3.set_ylabel('Cumulative Return')
    
    plt.tight_layout()
    plt.show()

def main():
    # 设置时间范围
    end_date = datetime.datetime.now()
    start_date = end_date - datetime.timedelta(days=365*2)  # 获取两年的数据
    
    # 获取数据
    treasury_data = get_treasury_yields(start_date, end_date)
    fx_data = get_fx_rate(start_date, end_date)
    jpy_rate = get_jpy_rate(start_date, end_date)
    
    # 合并数据
    if treasury_data is not None and fx_data is not None and jpy_rate is not None:
        data = pd.concat([treasury_data, fx_data, jpy_rate], axis=1)
        data = data.dropna()  # 删除缺失值
        
        # 计算carry trade收益
        data = calculate_carry_trade(data)
        
        # 输出基本统计信息
        print("\n基本统计信息:")
        print(data.describe())
        
        # 绘制图表
        plot_results(data)
        
        return data
    else:
        print("数据获取失败")
        return None

# 运行程序
if __name__ == "__main__":
    data = main()
