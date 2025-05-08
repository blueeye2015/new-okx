WITH daily_returns AS (
    SELECT 
        trade_date,
        (close - open) / open * 100 as daily_return,
        CASE WHEN close > open THEN 1 ELSE 0 END as is_up,
        -- 年末标记（12月最后一个交易日）
        CASE WHEN 
            EXTRACT(MONTH FROM trade_date) = 12 
            AND trade_date = DATE_TRUNC('MONTH', trade_date) + INTERVAL '1 MONTH - 1 day'
        THEN 1 ELSE 0 END as is_year_end,
        -- 季末标记（3,6,9,12月最后一个交易日）
        CASE WHEN 
            EXTRACT(MONTH FROM trade_date) IN (3,6,9,12)
            AND trade_date = DATE_TRUNC('MONTH', trade_date) + INTERVAL '1 MONTH - 1 day'
        THEN 1 ELSE 0 END as is_quarter_end,
        -- 月末标记
        CASE WHEN 
            trade_date = DATE_TRUNC('MONTH', trade_date) + INTERVAL '1 MONTH - 1 day'
        THEN 1 ELSE 0 END as is_month_end,
        -- 月初标记（用于对比）
        CASE WHEN 
            trade_date = DATE_TRUNC('MONTH', trade_date)
        THEN 1 ELSE 0 END as is_month_start,
        -- 记录具体是几月
        EXTRACT(MONTH FROM trade_date) as month
    FROM crypto_prices
)
select * into TEMPORARY daily_returns from daily_returns
-- 1. 总体统计
SELECT 
    '年末' as period_type,
    COUNT(*) as total_days,
    ROUND(AVG(daily_return)::numeric, 2) as avg_return,
    ROUND(COUNT(CASE WHEN is_up = 1 THEN 1 END) * 100.0 / COUNT(*), 2) as win_rate,
    ROUND(AVG(CASE WHEN is_up = 1 THEN daily_return ELSE NULL END)::numeric, 2) as avg_gain,
    ROUND(AVG(CASE WHEN is_up = 0 THEN daily_return ELSE NULL END)::numeric, 2) as avg_loss
FROM daily_returns
WHERE is_year_end = 1

UNION ALL

SELECT 
    '季末' as period_type,
    COUNT(*) as total_days,
    ROUND(AVG(daily_return)::numeric, 2) as avg_return,
    ROUND(COUNT(CASE WHEN is_up = 1 THEN 1 END) * 100.0 / COUNT(*), 2) as win_rate,
    ROUND(AVG(CASE WHEN is_up = 1 THEN daily_return ELSE NULL END)::numeric, 2) as avg_gain,
    ROUND(AVG(CASE WHEN is_up = 0 THEN daily_return ELSE NULL END)::numeric, 2) as avg_loss
FROM daily_returns
WHERE is_quarter_end = 1

UNION ALL

SELECT 
    '月末' as period_type,
    COUNT(*) as total_days,
    ROUND(AVG(daily_return)::numeric, 2) as avg_return,
    ROUND(COUNT(CASE WHEN is_up = 1 THEN 1 END) * 100.0 / COUNT(*), 2) as win_rate,
    ROUND(AVG(CASE WHEN is_up = 1 THEN daily_return ELSE NULL END)::numeric, 2) as avg_gain,
    ROUND(AVG(CASE WHEN is_up = 0 THEN daily_return ELSE NULL END)::numeric, 2) as avg_loss
FROM daily_returns
WHERE is_month_end = 1

UNION ALL

SELECT 
    '月初' as period_type,
    COUNT(*) as total_days,
    ROUND(AVG(daily_return)::numeric, 2) as avg_return,
    ROUND(COUNT(CASE WHEN is_up = 1 THEN 1 END) * 100.0 / COUNT(*), 2) as win_rate,
    ROUND(AVG(CASE WHEN is_up = 1 THEN daily_return ELSE NULL END)::numeric, 2) as avg_gain,
    ROUND(AVG(CASE WHEN is_up = 0 THEN daily_return ELSE NULL END)::numeric, 2) as avg_loss
FROM daily_returns
WHERE is_month_start = 1

UNION ALL

SELECT 
    '普通交易日' as period_type,
    COUNT(*) as total_days,
    ROUND(AVG(daily_return)::numeric, 2) as avg_return,
    ROUND(COUNT(CASE WHEN is_up = 1 THEN 1 END) * 100.0 / COUNT(*), 2) as win_rate,
    ROUND(AVG(CASE WHEN is_up = 1 THEN daily_return ELSE NULL END)::numeric, 2) as avg_gain,
    ROUND(AVG(CASE WHEN is_up = 0 THEN daily_return ELSE NULL END)::numeric, 2) as avg_loss
FROM daily_returns
WHERE is_month_end = 0 AND is_month_start = 0;

-- 2. 按月份分析月末表现
SELECT 
    month,
    COUNT(*) as total_days,
    ROUND(AVG(daily_return)::numeric, 2) as avg_return,
    ROUND(COUNT(CASE WHEN is_up = 1 THEN 1 END) * 100.0 / COUNT(*), 2) as win_rate,
    ROUND(AVG(CASE WHEN is_up = 1 THEN daily_return ELSE NULL END)::numeric, 2) as avg_gain,
    ROUND(AVG(CASE WHEN is_up = 0 THEN daily_return ELSE NULL END)::numeric, 2) as avg_loss
FROM daily_returns
WHERE is_month_end = 1
GROUP BY month
ORDER BY month;

-- 3. 分析前后走势
WITH period_analysis AS (
    SELECT 
        trade_date,
        daily_return,
        is_up,
        -- 获取前5天和后5天的平均收益率
        AVG(daily_return) OVER (
            ORDER BY trade_date
            ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
        ) as prev_5d_return,
        AVG(daily_return) OVER (
            ORDER BY trade_date
            ROWS BETWEEN 1 FOLLOWING AND 5 FOLLOWING
        ) as next_5d_return,
        is_month_end,
        is_quarter_end,
        is_year_end
    FROM daily_returns
)
SELECT 
    CASE 
        WHEN is_year_end = 1 THEN '年末'
        WHEN is_quarter_end = 1 THEN '季末'
        WHEN is_month_end = 1 THEN '月末'
        ELSE '普通交易日'
    END as period_type,
    COUNT(*) as total_samples,
    ROUND(AVG(prev_5d_return)::numeric, 2) as avg_prev_5d_return,
    ROUND(AVG(daily_return)::numeric, 2) as avg_current_return,
    ROUND(AVG(next_5d_return)::numeric, 2) as avg_next_5d_return
FROM period_analysis
WHERE is_month_end = 1 OR is_quarter_end = 1 OR is_year_end = 1
GROUP BY 
    CASE 
        WHEN is_year_end = 1 THEN '年末'
        WHEN is_quarter_end = 1 THEN '季末'
        WHEN is_month_end = 1 THEN '月末'
        ELSE '普通交易日'
    END;
