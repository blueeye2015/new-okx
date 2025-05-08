   with  daily_stats as (  SELECT 
          EXTRACT(MONTH FROM trade_date) as month,
          EXTRACT(DAY FROM trade_date) as day,
          (close - LAG(close) OVER (ORDER BY trade_date)) / LAG(close) OVER (ORDER BY trade_date) * 100 as daily_return,
          CASE WHEN close > LAG(close) OVER (ORDER BY trade_date) THEN 1 ELSE 0 END as is_up
      FROM crypto_prices
  ),
  daily_probability AS (
      SELECT 
          month,
          day,
          COUNT(*) as total_days,
          ROUND(AVG(CASE WHEN is_up = 1 THEN 1.0 ELSE 0 END) * 100, 2) as win_rate,
          ROUND(AVG(daily_return)::numeric, 2) as avg_return,
          ROUND(MAX(daily_return)::numeric, 2) as max_return,
          ROUND(MIN(daily_return)::numeric, 2) as min_return,
          ROUND(STDDEV(daily_return)::numeric, 2) as volatility
      FROM daily_stats
      GROUP BY month, day
  )
  select * into TEMPORARY daily_probability from daily_probability
  SELECT 
      month,
      day,
      total_days,
      win_rate as "上涨概率(%)",
      avg_return as "平均收益率(%)",
      max_return as "最大上涨(%)",
      min_return as "最大下跌(%)",
      volatility as "波动率(%)",
      CASE 
          WHEN win_rate >= 60 THEN '强势日期'
          WHEN win_rate <= 40 THEN '弱势日期'
          ELSE '中性日期'
      END as "日期强弱"
  FROM daily_probability
  ORDER BY 
      month, 
      day;

  -- 按月份统计概览
  SELECT 
      month,
      ROUND(AVG(win_rate), 2) as avg_win_rate,
      ROUND(AVG(avg_return), 2) as avg_monthly_return,
      COUNT(*) as days_in_month,
      COUNT(CASE WHEN win_rate >= 55 THEN 1 END) as strong_days,
      COUNT(CASE WHEN win_rate <= 45 THEN 1 END) as weak_days
  FROM daily_probability
  GROUP BY month
  ORDER BY month;

  -- 找出最强和最弱的日期（Top 10）
  (SELECT 
      month,
      day,
      win_rate,
      avg_return,
      'Top强势日期' as type
  FROM daily_probability
  ORDER BY win_rate DESC
  LIMIT 10)
  UNION ALL
  (SELECT 
      month,
      day,
      win_rate,
      avg_return,
      'Top弱势日期' as type
  FROM daily_probability
  ORDER BY win_rate ASC
  LIMIT 10)
  ORDER BY type, win_rate DESC;

  -- 按周分析（周一到周五的表现）
  WITH daily_dow AS (
      SELECT 
          EXTRACT(DOW FROM trade_date) as day_of_week,
          (close - LAG(close) OVER (ORDER BY trade_date)) / LAG(close) OVER (ORDER BY trade_date) * 100 as daily_return,
          CASE WHEN close > LAG(close) OVER (ORDER BY trade_date) THEN 1 ELSE 0 END as is_up
      FROM crypto_prices
  )
  SELECT 
      CASE day_of_week
          WHEN 0 THEN '周日'
          WHEN 1 THEN '周一'
          WHEN 2 THEN '周二'
          WHEN 3 THEN '周三'
          WHEN 4 THEN '周四'
          WHEN 5 THEN '周五'
          WHEN 6 THEN '周六'
      END as weekday,
      COUNT(*) as total_days,
      ROUND(AVG(CASE WHEN is_up = 1 THEN 1.0 ELSE 0 END) * 100, 2) as win_rate,
      ROUND(AVG(daily_return)::numeric, 2) as avg_return
  FROM daily_dow
  GROUP BY day_of_week
  ORDER BY day_of_week;