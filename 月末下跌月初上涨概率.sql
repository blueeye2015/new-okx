with daily_returns as (
   SELECT 
          trade_date,
          (close - LAG(close) OVER (ORDER BY trade_date)) / LAG(close) OVER (ORDER BY trade_date) * 100 as daily_return,
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
  -- 找出月末和下月初的配对
  month_pairs AS (
      SELECT 
          m1.trade_date as month_end_date,
          m1.daily_return as month_end_return,
          m2.trade_date as next_month_start_date,
          m2.daily_return as next_month_start_return
      FROM daily_returns m1
      LEFT JOIN daily_returns m2 
      ON m2.trade_date > m1.trade_date 
      AND m2.is_month_start = 1 
      AND m2.trade_date = DATE_TRUNC('MONTH', m1.trade_date + INTERVAL '1 day')
      WHERE m1.is_month_end = 1
  ) select * into TEMPORARY month_pairs from month_pairs
  -- 计算概率统计
  SELECT 
      -- 总体统计
      COUNT(*) as total_pairs,
      -- 月末下跌的情况
      COUNT(CASE WHEN month_end_return < 0 THEN 1 END) as month_end_down_count,
      -- 月末下跌且次月初上涨的情况
      COUNT(CASE WHEN month_end_return < 0 AND next_month_start_return > 0 THEN 1 END) as down_then_up_count,
      -- 计算概率
      ROUND(
          COUNT(CASE WHEN month_end_return < 0 AND next_month_start_return > 0 THEN 1 END)::NUMERIC / 
          NULLIF(COUNT(CASE WHEN month_end_return < 0 THEN 1 END), 0) * 100,
          2
      ) as probability_down_then_up,
      -- 平均涨跌幅
      ROUND(AVG(CASE WHEN month_end_return < 0 THEN next_month_start_return END)::NUMERIC, 2) as avg_next_day_return_after_down,
      -- 最大上涨
      ROUND(MAX(CASE WHEN month_end_return < 0 THEN next_month_start_return END)::NUMERIC, 2) as max_up_after_down,
      -- 最大下跌
      ROUND(MIN(CASE WHEN month_end_return < 0 THEN next_month_start_return END)::NUMERIC, 2) as max_down_after_down
  FROM month_pairs;

  -- 按年度分析趋势
  SELECT 
      EXTRACT(YEAR FROM month_end_date) as year,
      COUNT(*) as total_pairs,
      COUNT(CASE WHEN month_end_return < 0 THEN 1 END) as month_end_down_count,
      COUNT(CASE WHEN month_end_return < 0 AND next_month_start_return > 0 THEN 1 END) as down_then_up_count,
      ROUND(
          COUNT(CASE WHEN month_end_return < 0 AND next_month_start_return > 0 THEN 1 END)::NUMERIC / 
          NULLIF(COUNT(CASE WHEN month_end_return < 0 THEN 1 END), 0) * 100,
          2
      ) as probability_down_then_up
  FROM month_pairs
  GROUP BY EXTRACT(YEAR FROM month_end_date)
  ORDER BY EXTRACT(YEAR FROM month_end_date);