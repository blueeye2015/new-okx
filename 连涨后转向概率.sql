WITH price_moves AS (
    SELECT 
        trade_date,
        (close - open) / open * 100 as daily_return,
        CASE WHEN close > open THEN 1 ELSE 0 END as is_up
    FROM crypto_prices
),
-- 标记连续涨跌的开始
streak_starts AS (
    SELECT 
        trade_date,
        daily_return,
        is_up,
        CASE 
            WHEN is_up != LAG(is_up, 1, NULL) OVER (ORDER BY trade_date) 
            THEN 1 ELSE 0 
        END as new_streak
    FROM price_moves
),
-- 给每个连续序列分配组号
streak_groups AS (
    SELECT 
        trade_date,
        daily_return,
        is_up,
        SUM(new_streak) OVER (ORDER BY trade_date) as streak_id
    FROM streak_starts
),
-- 计算每个组的连续天数
streak_lengths AS (
    SELECT 
        *,
        COUNT(*) OVER (PARTITION BY streak_id) as streak_length,
        LEAD(is_up) OVER (ORDER BY trade_date) as next_day_is_up,
        LEAD(daily_return) OVER (ORDER BY trade_date) as next_day_return
    FROM streak_groups
)
select * into TEMPORARY streak_lengths from streak_lengths
-- 1. 分析连续上涨后的转向概率
SELECT 
    streak_length as consecutive_up_days,
    COUNT(*) as total_cases,
    ROUND(AVG(CASE WHEN next_day_is_up = 0 THEN 1.0 ELSE 0 END) * 100, 2) as reversal_probability,
    ROUND(AVG(next_day_return)::numeric, 2) as avg_next_day_return,
    ROUND(MIN(next_day_return)::numeric, 2) as min_next_day_return,
    ROUND(MAX(next_day_return)::numeric, 2) as max_next_day_return
FROM streak_lengths
WHERE is_up = 1 
    AND streak_length BETWEEN 1 AND 10
    AND next_day_return IS NOT NULL
GROUP BY streak_length
ORDER BY streak_length;

-- 2. 分析连续下跌后的转向概率
SELECT 
    streak_length as consecutive_down_days,
    COUNT(*) as total_cases,
    ROUND(AVG(CASE WHEN next_day_is_up = 1 THEN 1.0 ELSE 0 END) * 100, 2) as reversal_probability,
    ROUND(AVG(next_day_return)::numeric, 2) as avg_next_day_return,
    ROUND(MIN(next_day_return)::numeric, 2) as min_next_day_return,
    ROUND(MAX(next_day_return)::numeric, 2) as max_next_day_return
FROM streak_lengths
WHERE is_up = 0 
    AND streak_length BETWEEN 1 AND 10
    AND next_day_return IS NOT NULL
GROUP BY streak_length
ORDER BY streak_length;

-- 3. 分析极端连续涨跌的情况（连续5天以上）
SELECT 
    CASE WHEN is_up = 1 THEN '连续上涨' ELSE '连续下跌' END as streak_type,
    streak_length,
    trade_date,
    daily_return as current_day_return,
    next_day_return
FROM streak_lengths
WHERE streak_length >= 5
    AND next_day_return IS NOT NULL
ORDER BY streak_length DESC, trade_date;
