WITH daily_returns AS (
    SELECT 
        trade_date,
        week_period,
        close,
        close / LAG(close) OVER (ORDER BY trade_date) - 1 as daily_return
    FROM crypto_prices
),
consecutive_pattern AS (
    SELECT 
        trade_date,
        week_period,
        daily_return,
        LAG(daily_return) OVER (ORDER BY trade_date) as prev_day_return,
        LEAD(daily_return) OVER (ORDER BY trade_date) as next_day_return
    FROM daily_returns
)
SELECT 
    week_period,
    CASE 
        WHEN prev_day_return > 0 AND daily_return > 0 THEN '连续上涨'
        WHEN prev_day_return < 0 AND daily_return < 0 THEN '连续下跌'
        WHEN prev_day_return < 0 AND daily_return > 0 THEN '先跌后涨'
        ELSE '先涨后跌'
    END as pattern,
    COUNT(*) as cases,
    ROUND((AVG(next_day_return) * 100)::numeric, 2) as avg_next_return,
    ROUND((COUNT(CASE WHEN next_day_return > 0 THEN 1 END) * 100.0 / COUNT(*))::numeric, 2) as next_day_win_rate,
    -- 添加平均涨跌幅度
    ROUND((AVG(daily_return) * 100)::numeric, 2) as avg_current_return,
    ROUND((AVG(ABS(daily_return)) * 100)::numeric, 2) as avg_movement
FROM consecutive_pattern
WHERE 
     prev_day_return IS NOT NULL 
    AND next_day_return IS NOT NULL
GROUP BY 1, 2
ORDER BY 
     week_period,
    pattern;

-- 分析不同时间段的连续涨跌
WITH time_pattern AS (
    SELECT 
        trade_date,
        week_period,
        EXTRACT(HOUR FROM trade_time) as hour,
        close / LAG(close) OVER (ORDER BY trade_date, trade_time) - 1 as hourly_return
    FROM crypto_prices
    WHERE week_period IN ('周五', '周六', '周一')
)
SELECT 
    week_period,
    CASE 
        WHEN hour < 8 THEN '凌晨(0-8点)'
        WHEN hour < 16 THEN '白天(8-16点)'
        ELSE '晚上(16-24点)'
    END as time_period,
    COUNT(*) as total_cases,
    ROUND((AVG(hourly_return) * 100)::numeric, 2) as avg_return,
    ROUND((COUNT(CASE WHEN hourly_return > 0 THEN 1 END) * 100.0 / COUNT(*))::numeric, 2) as win_rate
FROM time_pattern
WHERE hourly_return IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;

-- 分析周五到周一的持续性趋势
WITH trend_analysis AS (
    SELECT 
        trade_date,
        week_period,
        close,
        close / LAG(close) OVER (ORDER BY trade_date) - 1 as daily_return,
        SUM(CASE WHEN close / LAG(close) OVER (ORDER BY trade_date) - 1 > 0 THEN 1 ELSE -1 END) 
            OVER (ORDER BY trade_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) as trend_strength
    FROM crypto_prices
    WHERE week_period IN ('周五', '周六', '周一')
)
SELECT 
    week_period,
    CASE 
        WHEN trend_strength = 3 THEN '强势上涨'
        WHEN trend_strength = -3 THEN '强势下跌'
        WHEN trend_strength > 0 THEN '偏强'
        WHEN trend_strength < 0 THEN '偏弱'
        ELSE '盘整'
    END as trend_type,
    COUNT(*) as cases,
    ROUND((AVG(daily_return) * 100)::numeric, 2) as avg_return
FROM trend_analysis
WHERE trend_strength IS NOT NULL
GROUP BY 1, 2
ORDER BY 1, 2;
