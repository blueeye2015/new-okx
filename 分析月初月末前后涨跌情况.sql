WITH daily_returns AS (
    SELECT 
        trade_date,
        (close - open) / open * 100 as daily_return,
        close,
        open,
        high,
        low,
        volume,
        CASE WHEN close > open THEN 1 ELSE 0 END as is_up,
        -- 波动性指标
        (high - low) / open * 100 as daily_range,
        -- 年末标记
        CASE WHEN 
            EXTRACT(MONTH FROM trade_date) = 12 
            AND trade_date = DATE_TRUNC('MONTH', trade_date) + INTERVAL '1 MONTH - 1 day'
        THEN 1 ELSE 0 END as is_year_end,
        -- 季末标记
        CASE WHEN 
            EXTRACT(MONTH FROM trade_date) IN (3,6,9,12)
            AND trade_date = DATE_TRUNC('MONTH', trade_date) + INTERVAL '1 MONTH - 1 day'
        THEN 1 ELSE 0 END as is_quarter_end,
        -- 月末标记
        CASE WHEN 
            trade_date = DATE_TRUNC('MONTH', trade_date) + INTERVAL '1 MONTH - 1 day'
        THEN 1 ELSE 0 END as is_month_end,
        -- 月初标记
        CASE WHEN 
            trade_date = DATE_TRUNC('MONTH', trade_date)
        THEN 1 ELSE 0 END as is_month_start
    FROM crypto_prices
),
-- 计算前后5天的数据
period_stats AS (
    SELECT 
        *,
        -- 前5天累计涨跌幅
        100 * (close / LAG(close, 5) OVER (ORDER BY trade_date) - 1) as prev_5d_change,
        -- 前5天波动率
        AVG(daily_range) OVER (ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING) as prev_5d_volatility,
        -- 前5天成交量变化
        volume / NULLIF(AVG(volume) OVER (ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING), 0) as volume_ratio,
        -- 前5天最高价和最低价
        MAX(high) OVER (ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING) as prev_5d_high,
        MIN(low) OVER (ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING) as prev_5d_low
    FROM daily_returns
)
select * into TEMPORARY period_stats from period_stats
-- 1. 分析各时期的详细统计
SELECT 
    CASE 
        WHEN is_year_end = 1 THEN '年末'
        WHEN is_quarter_end = 1 THEN '季末'
        WHEN is_month_end = 1 THEN '月末'
        WHEN is_month_start = 1 THEN '月初'
        ELSE '普通交易日'
    END as period_type,
    COUNT(*) as total_days,
    -- 基础统计
    ROUND(AVG(daily_return)::numeric, 2) as avg_return,
    ROUND(COUNT(CASE WHEN is_up = 1 THEN 1 END) * 100.0 / COUNT(*), 2) as win_rate,
    -- 波动性指标
    ROUND(AVG(daily_range)::numeric, 2) as avg_range,
    ROUND(STDDEV(daily_return)::numeric, 2) as return_std,
    -- 成交量分析
    ROUND(AVG(volume_ratio)::numeric, 2) as avg_volume_ratio,
    -- 前期趋势
    ROUND(AVG(prev_5d_change)::numeric, 2) as avg_prev_5d_change,
    ROUND(AVG(prev_5d_volatility)::numeric, 2) as avg_prev_5d_volatility,
    -- 极值分析
    ROUND(MAX(daily_return)::numeric, 2) as max_return,
    ROUND(MIN(daily_return)::numeric, 2) as min_return
FROM period_stats
GROUP BY 
    CASE 
        WHEN is_year_end = 1 THEN '年末'
        WHEN is_quarter_end = 1 THEN '季末'
        WHEN is_month_end = 1 THEN '月末'
        WHEN is_month_start = 1 THEN '月初'
        ELSE '普通交易日'
    END
ORDER BY 
    CASE 
        WHEN CASE 
            WHEN is_year_end = 1 THEN '年末'
            WHEN is_quarter_end = 1 THEN '季末'
            WHEN is_month_end = 1 THEN '月末'
            WHEN is_month_start = 1 THEN '月初'
            ELSE '普通交易日'
        END = '年末' THEN 1
        WHEN CASE 
            WHEN is_year_end = 1 THEN '年末'
            WHEN is_quarter_end = 1 THEN '季末'
            WHEN is_month_end = 1 THEN '月末'
            WHEN is_month_start = 1 THEN '月初'
            ELSE '普通交易日'
        END = '季末' THEN 2
        WHEN CASE 
            WHEN is_year_end = 1 THEN '年末'
            WHEN is_quarter_end = 1 THEN '季末'
            WHEN is_month_end = 1 THEN '月末'
            WHEN is_month_start = 1 THEN '月初'
            ELSE '普通交易日'
        END = '月末' THEN 3
        WHEN CASE 
            WHEN is_year_end = 1 THEN '年末'
            WHEN is_quarter_end = 1 THEN '季末'
            WHEN is_month_end = 1 THEN '月末'
            WHEN is_month_start = 1 THEN '月初'
            ELSE '普通交易日'
        END = '月初' THEN 4
        ELSE 5
    END;

-- 2. 分析胜率与前期走势的关系
WITH win_rate_analysis AS (
    SELECT 
        CASE 
            WHEN prev_5d_change <= -10 THEN '大幅下跌(≤-10%)'
            WHEN prev_5d_change <= -5 THEN '中幅下跌(-10%~-5%)'
            WHEN prev_5d_change <= 0 THEN '小幅下跌(-5%~0%)'
            WHEN prev_5d_change <= 5 THEN '小幅上涨(0%~5%)'
            WHEN prev_5d_change <= 10 THEN '中幅上涨(5%~10%)'
            ELSE '大幅上涨(>10%)'
        END as trend_category,
        CASE 
            WHEN is_year_end = 1 THEN '年末'
            WHEN is_quarter_end = 1 THEN '季末'
            WHEN is_month_end = 1 THEN '月末'
            WHEN is_month_start = 1 THEN '月初'
            ELSE '普通交易日'
        END as period_type,
        COUNT(*) as total_cases,
        ROUND(AVG(CASE WHEN is_up = 1 THEN 1.0 ELSE 0 END) * 100, 2) as win_rate,
        ROUND(AVG(daily_return)::numeric, 2) as avg_return
    FROM period_stats
    WHERE prev_5d_change IS NOT NULL
    GROUP BY 1, 2
)
SELECT 
    trend_category,
    period_type,
    total_cases,
    win_rate,
    avg_return
FROM win_rate_analysis
WHERE period_type IN ('年末', '季末', '月末', '月初')
ORDER BY 
    CASE period_type
        WHEN '年末' THEN 1
        WHEN '季末' THEN 2
        WHEN '月末' THEN 3
        WHEN '月初' THEN 4
        ELSE 5
    END,
    CASE trend_category
        WHEN '大幅下跌(≤-10%)' THEN 1
        WHEN '中幅下跌(-10%~-5%)' THEN 2
        WHEN '小幅下跌(-5%~0%)' THEN 3
        WHEN '小幅上涨(0%~5%)' THEN 4
        WHEN '中幅上涨(5%~10%)' THEN 5
        ELSE 6
    END;

-- 3. 分析成交量与胜率的关系
WITH volume_analysis AS (
    SELECT 
        CASE 
            WHEN volume_ratio <= 0.5 THEN '成交量大幅萎缩(<50%)'
            WHEN volume_ratio <= 0.8 THEN '成交量轻微萎缩(50%-80%)'
            WHEN volume_ratio <= 1.2 THEN '成交量正常(80%-120%)'
            WHEN volume_ratio <= 2.0 THEN '成交量放大(120%-200%)'
            ELSE '成交量剧增(>200%)'
        END as volume_category,
        CASE 
            WHEN is_year_end = 1 THEN '年末'
            WHEN is_quarter_end = 1 THEN '季末'
            WHEN is_month_end = 1 THEN '月末'
            WHEN is_month_start = 1 THEN '月初'
            ELSE '普通交易日'
        END as period_type,
        COUNT(*) as total_cases,
        ROUND(AVG(CASE WHEN is_up = 1 THEN 1.0 ELSE 0 END) * 100, 2) as win_rate,
        ROUND(AVG(daily_return)::numeric, 2) as avg_return
    FROM period_stats
    WHERE volume_ratio IS NOT NULL
    GROUP BY 1, 2
)
SELECT 
    volume_category,
    period_type,
    total_cases,
    win_rate,
    avg_return
FROM volume_analysis
WHERE period_type IN ('年末', '季末', '月末', '月初')
ORDER BY 
    CASE period_type
        WHEN '年末' THEN 1
        WHEN '季末' THEN 2
        WHEN '月末' THEN 3
        WHEN '月初' THEN 4
        ELSE 5
    END,
    CASE volume_category
        WHEN '成交量大幅萎缩(<50%)' THEN 1
        WHEN '成交量轻微萎缩(50%-80%)' THEN 2
        WHEN '成交量正常(80%-120%)' THEN 3
        WHEN '成交量放大(120%-200%)' THEN 4
        ELSE 5
    END;
