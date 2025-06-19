with base_metrics as (
	SELECT 
          trade_date,
          close,
          open,
          high,
          low,
          volume,
          -- 基础涨跌信息
          (close - open) / open * 100 as daily_return,
          CASE WHEN close > open THEN 1 ELSE 0 END as is_up,
          -- 日期特征
          EXTRACT(MONTH FROM trade_date) as month,
          EXTRACT(DAY FROM trade_date) as day,
          EXTRACT(DOW FROM trade_date) as day_of_week,
          -- 月末/月初标记
          CASE WHEN trade_date = DATE_TRUNC('MONTH', trade_date) + INTERVAL '1 MONTH - 1 day'
              THEN 1 ELSE 0 END as is_month_end,
          CASE WHEN trade_date = DATE_TRUNC('MONTH', trade_date)
              THEN 1 ELSE 0 END as is_month_start,
          -- 季末标记
          CASE WHEN EXTRACT(MONTH FROM trade_date) IN (3,6,9,12) 
              AND trade_date = DATE_TRUNC('MONTH', trade_date) + INTERVAL '1 MONTH - 1 day'
              THEN 1 ELSE 0 END as is_quarter_end,
          -- 波动率
          (high - low) / open * 100 as daily_range,
          -- 成交量变化
          volume / LAG(volume, 1) OVER (ORDER BY trade_date) - 1 as volume_change,
          -- 移动平均
          AVG(close) OVER (ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as ma5,
          AVG(close) OVER (ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) as ma20,
          AVG(volume) OVER (ORDER BY trade_date ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) as vol_ma5,
          -- 连续涨跌计数
          SUM(CASE WHEN close > open THEN 1 ELSE 0 END) 
              OVER (ORDER BY trade_date ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) as up_streak
      FROM crypto_prices
  )
select * into TEMPORARY base_metrics from  base_metrics 
  -- 1. 日历效应概率
  with calendar_prob AS (
      SELECT 
          month,
          day,
          day_of_week,
          AVG(CASE WHEN is_up = 1 THEN 1.0 ELSE 0 END) as calendar_prob
      FROM base_metrics
      GROUP BY month, day, day_of_week
  )select * into TEMPORARY calendar_prob from  calendar_prob 
  -- 2. 连续涨跌后的转向概率
with  streak_prob AS (
      SELECT 
          up_streak,
          AVG(CASE WHEN is_up = 1 THEN 1.0 ELSE 0 END) as streak_prob,
          COUNT(*) as streak_count
      FROM base_metrics
      WHERE up_streak IS NOT NULL
      GROUP BY up_streak
  )select * into TEMPORARY streak_prob from  streak_prob 
  -- 3. 成交量变化对应的涨跌概率
 with volume_prob AS (
      SELECT 
          CASE 
              WHEN volume_change <= -0.2 THEN 1
              WHEN volume_change <= -0.1 THEN 2
              WHEN volume_change <= 0 THEN 3
              WHEN volume_change <= 0.1 THEN 4
              WHEN volume_change <= 0.2 THEN 5
              ELSE 6
          END as volume_category,
          AVG(CASE WHEN is_up = 1 THEN 1.0 ELSE 0 END) as volume_prob
      FROM base_metrics
      WHERE volume_change IS NOT NULL
      GROUP BY 1
  ) select * into TEMPORARY volume_prob from  volume_prob 
  -- 4. 技术指标概率
with  technical_prob AS (
      SELECT 
          trade_date,
          -- MA交叉情况
          CASE WHEN close > ma5 AND ma5 > ma20 THEN 1
               WHEN close < ma5 AND ma5 < ma20 THEN 0
               ELSE 0.5 END as ma_signal,
          -- 成交量趋势
          CASE WHEN volume > vol_ma5 THEN 1 ELSE 0 END as vol_trend,
          -- 波动率分类
          NTILE(5) OVER (ORDER BY daily_range) as volatility_quintile
      FROM base_metrics
  ) select * into TEMPORARY technical_prob from  technical_prob
  -- 最终综合分析
  final_prediction AS (
      SELECT 
          b.trade_date,
          b.is_up as actual_result,
          -- 各个维度的概率
          c.calendar_prob,
          s.streak_prob,
          v.volume_prob,
          t.ma_signal as technical_prob,
          -- 计算综合概率 (加权平均)
          (COALESCE(c.calendar_prob, 0.5) * 0.2 + 
           COALESCE(s.streak_prob, 0.5) * 0.3 + 
           COALESCE(v.volume_prob, 0.5) * 0.2 + 
           COALESCE(t.ma_signal, 0.5) * 0.3) as composite_probability,
          -- 特殊日期标记
          b.is_month_end,
          b.is_month_start,
          b.is_quarter_end
      FROM base_metrics b
      LEFT JOIN calendar_prob c 
          ON b.month = c.month AND b.day = c.day AND b.day_of_week = c.day_of_week
      LEFT JOIN streak_prob s 
          ON b.up_streak = s.up_streak
      LEFT JOIN volume_prob v 
          ON CASE 
              WHEN b.volume_change <= -0.2 THEN 1
              WHEN b.volume_change <= -0.1 THEN 2
              WHEN b.volume_change <= 0 THEN 3
              WHEN b.volume_change <= 0.1 THEN 4
              WHEN b.volume_change <= 0.2 THEN 5
              ELSE 6
             END = v.volume_category
      LEFT JOIN technical_prob t 
          ON b.trade_date = t.trade_date
  ) 
  select * into TEMPORARY final_prediction from final_prediction
  -- 输出模型准确性评估
  SELECT 
      -- 总体准确率
      ROUND(AVG(CASE WHEN (composite_probability >= 0.5 AND actual_result = 1) OR
                         (composite_probability < 0.5 AND actual_result = 0)
                    THEN 1.0 ELSE 0 END) * 100, 2) as overall_accuracy,
      -- 按概率区间的准确性
      probability_range,
      COUNT(*) as sample_count,
      ROUND(AVG(actual_result) * 100, 2) as actual_up_rate,
      ROUND(AVG(CASE WHEN (composite_probability >= 0.5 AND actual_result = 1) OR
                         (composite_probability < 0.5 AND actual_result = 0)
                    THEN 1.0 ELSE 0 END) * 100, 2) as accuracy_rate
  FROM (
      SELECT 
          *,
          CASE 
              WHEN composite_probability >= 0.7 THEN '强买入信号(≥70%)'
              WHEN composite_probability >= 0.6 THEN '买入信号(60-70%)'
              WHEN composite_probability >= 0.5 THEN '弱买入信号(50-60%)'
              WHEN composite_probability >= 0.4 THEN '弱卖出信号(40-50%)'
              WHEN composite_probability >= 0.3 THEN '卖出信号(30-40%)'
              ELSE '强卖出信号(<30%)'
          END as probability_range
      FROM final_prediction
  ) t
  GROUP BY probability_range
  ORDER BY 
      CASE probability_range
          WHEN '强买入信号(≥70%)' THEN 1
          WHEN '买入信号(60-70%)' THEN 2
          WHEN '弱买入信号(50-60%)' THEN 3
          WHEN '弱卖出信号(40-50%)' THEN 4
          WHEN '卖出信号(30-40%)' THEN 5
          WHEN '强卖出信号(<30%)' THEN 6
      END;

  -- 输出最新一天的预测
  SELECT 
      trade_date,
      ROUND(composite_probability * 100, 2) as up_probability,
      CASE 
          WHEN composite_probability >= 0.7 THEN '强买入信号'
          WHEN composite_probability >= 0.6 THEN '买入信号'
          WHEN composite_probability >= 0.5 THEN '弱买入信号'
          WHEN composite_probability >= 0.4 THEN '弱卖出信号'
          WHEN composite_probability >= 0.3 THEN '卖出信号'
          ELSE '强卖出信号'
      END as signal,
      calendar_prob * 100 as calendar_factor,
      streak_prob * 100 as streak_factor,
      volume_prob * 100 as volume_factor,
      technical_prob * 100 as technical_factor
  FROM final_prediction
  order by trade_date desc
  WHERE trade_date = (SELECT MAX(trade_date) FROM base_metrics);


  select * from final_prediction
  select * from base_metrics
  select * from calendar_prob order by month,day_of_week

  with prediction_accuracy as (
	            SELECT 
          test_date,
          actual_result,
          predicted_probability,
          CASE WHEN (predicted_probability >= 0.5 AND actual_result = 1) OR
                    (predicted_probability < 0.5 AND actual_result = 0)
              THEN 1 ELSE 0 
          END as is_correct
      FROM (
          SELECT 
              b1.trade_date as test_date,
              b1.is_up as actual_result,
              (
                  COALESCE(
                      (SELECT AVG(CASE WHEN b2.is_up = 1 THEN 1.0 ELSE 0 END)
                       FROM base_metrics b2
                       WHERE b2.trade_date < b1.trade_date
                       AND b2.month = b1.month 
                       AND b2.day = b1.day
                       AND b2.day_of_week = b1.day_of_week) 
                  , 0.5) * 0.2 +
                  
                  COALESCE(
                      (SELECT AVG(CASE WHEN b2.is_up = 1 THEN 1.0 ELSE 0 END)
                       FROM base_metrics b2
                       WHERE b2.trade_date < b1.trade_date
                       AND b2.up_streak = b1.up_streak)
                  , 0.5) * 0.3 +
                  
                  COALESCE(
                      (SELECT AVG(CASE WHEN b2.is_up = 1 THEN 1.0 ELSE 0 END)
                       FROM base_metrics b2
                       WHERE b2.trade_date < b1.trade_date
                       AND CASE 
                           WHEN b2.volume_change <= -0.2 THEN 1
                           WHEN b2.volume_change <= -0.1 THEN 2
                           WHEN b2.volume_change <= 0 THEN 3
                           WHEN b2.volume_change <= 0.1 THEN 4
                           WHEN b2.volume_change <= 0.2 THEN 5
                           ELSE 6
                       END = 
                       CASE 
                           WHEN b1.volume_change <= -0.2 THEN 1
                           WHEN b1.volume_change <= -0.1 THEN 2
                           WHEN b1.volume_change <= 0 THEN 3
                           WHEN b1.volume_change <= 0.1 THEN 4
                           WHEN b1.volume_change <= 0.2 THEN 5
                           ELSE 6
                       END)
                  , 0.5) * 0.2 +
                  
                  COALESCE(
                      CASE WHEN b1.close > b1.ma5 AND b1.ma5 > b1.ma20 THEN 1
                           WHEN b1.close < b1.ma5 AND b1.ma5 < b1.ma20 THEN 0
                           ELSE 0.5 
                      END
                  , 0.5) * 0.3
              ) as predicted_probability
          FROM base_metrics b1
          WHERE b1.trade_date >= (SELECT MAX(trade_date) - INTERVAL '60 days' FROM base_metrics)
      ) predictions
  )
  SELECT 
      DATE_TRUNC('week', test_date) as week,
      COUNT(*) as total_predictions,
      ROUND(AVG(is_correct) * 100, 2) as accuracy_rate,
      ROUND(AVG(predicted_probability) * 100, 2) as avg_predicted_probability,
      ROUND(AVG(actual_result) * 100, 2) as actual_up_rate
  FROM prediction_accuracy
  GROUP BY DATE_TRUNC('week', test_date)
  ORDER BY week DESC;

  WITH latest_metrics AS (
      SELECT *
      FROM base_metrics
      WHERE trade_date = (SELECT MAX(trade_date) FROM base_metrics)
  ),
  next_day_prediction AS (
      SELECT 
          l.*,
          (
              COALESCE(
                  (SELECT AVG(CASE WHEN b.is_up = 1 THEN 1.0 ELSE 0 END)
                   FROM base_metrics b
                   WHERE EXTRACT(MONTH FROM b.trade_date) = EXTRACT(MONTH FROM l.trade_date + INTERVAL '1 day')
                   AND EXTRACT(DAY FROM b.trade_date) = EXTRACT(DAY FROM l.trade_date + INTERVAL '1 day')
                   AND EXTRACT(DOW FROM b.trade_date) = EXTRACT(DOW FROM l.trade_date + INTERVAL '1 day'))
              , 0.5) * 0.2 +
              
              COALESCE(
                  (SELECT AVG(CASE WHEN b.is_up = 1 THEN 1.0 ELSE 0 END)
                   FROM base_metrics b
                   WHERE b.up_streak = l.up_streak)
              , 0.5) * 0.3 +
              
              COALESCE(
                  (SELECT AVG(CASE WHEN b.is_up = 1 THEN 1.0 ELSE 0 END)
                   FROM base_metrics b
                   WHERE CASE 
                       WHEN b.volume_change <= -0.2 THEN 1
                       WHEN b.volume_change <= -0.1 THEN 2
                       WHEN b.volume_change <= 0 THEN 3
                       WHEN b.volume_change <= 0.1 THEN 4
                       WHEN b.volume_change <= 0.2 THEN 5
                       ELSE 6
                   END = 
                   CASE 
                       WHEN l.volume_change <= -0.2 THEN 1
                       WHEN l.volume_change <= -0.1 THEN 2
                       WHEN l.volume_change <= 0 THEN 3
                       WHEN l.volume_change <= 0.1 THEN 4
                       WHEN l.volume_change <= 0.2 THEN 5
                       ELSE 6
                   END)
              , 0.5) * 0.2 +
              
              COALESCE(
                  CASE WHEN l.close > l.ma5 AND l.ma5 > l.ma20 THEN 1
                       WHEN l.close < l.ma5 AND l.ma5 < l.ma20 THEN 0
                       ELSE 0.5 
                  END
              , 0.5) * 0.3
          ) as probability
      FROM latest_metrics l
  )
  SELECT 
      (SELECT MAX(trade_date) + INTERVAL '1 day' FROM base_metrics) as prediction_date,
      ROUND(probability * 100, 2) as next_day_up_probability,
      CASE 
          WHEN probability >= 0.7 THEN '强买入信号'
          WHEN probability >= 0.6 THEN '买入信号'
          WHEN probability >= 0.5 THEN '弱买入信号'
          WHEN probability >= 0.4 THEN '弱卖出信号'
          WHEN probability >= 0.3 THEN '卖出信号'
          ELSE '强卖出信号'
      END as signal
  FROM next_day_prediction;

    CREATE TABLE IF NOT EXISTS factor_performance (
      trade_date DATE NOT NULL,
      factor_name VARCHAR(50) NOT NULL,
      prediction NUMERIC NOT NULL,
      actual_result INTEGER NOT NULL,
      is_correct INTEGER NOT NULL,
      PRIMARY KEY (trade_date, factor_name)
  );
select * from factor_performance
select* from factor_weights
  -- 创建每日权重表（如果不存在）
  CREATE TABLE IF NOT EXISTS factor_weights (
      calculation_date DATE NOT NULL,
      factor_name VARCHAR(50) NOT NULL,
      weight NUMERIC NOT NULL,
      win_rate NUMERIC NOT NULL,
      PRIMARY KEY (calculation_date, factor_name)
  );

  -- 插入每日因子预测结果和实际结果
  WITH factor_predictions AS (
      SELECT 
          b1.trade_date,
          -- 日历效应因子
          COALESCE(
              (SELECT AVG(CASE WHEN b2.is_up = 1 THEN 1.0 ELSE 0 END)
               FROM base_metrics b2
               WHERE b2.trade_date < b1.trade_date
               AND b2.month = b1.month 
               AND b2.day = b1.day
               AND b2.day_of_week = b1.day_of_week) 
          , 0.5)::NUMERIC as calendar_prob,
          
          -- 连续涨跌因子
          COALESCE(
              (SELECT AVG(CASE WHEN b2.is_up = 1 THEN 1.0 ELSE 0 END)
               FROM base_metrics b2
               WHERE b2.trade_date < b1.trade_date
               AND b2.up_streak = b1.up_streak)
          , 0.5)::NUMERIC as streak_prob,
          
          -- 成交量分析因子
          COALESCE(
              (SELECT AVG(CASE WHEN b2.is_up = 1 THEN 1.0 ELSE 0 END)
               FROM base_metrics b2
               WHERE b2.trade_date < b1.trade_date
               AND CASE 
                   WHEN b2.volume_change <= -0.2 THEN 1
                   WHEN b2.volume_change <= -0.1 THEN 2
                   WHEN b2.volume_change <= 0 THEN 3
                   WHEN b2.volume_change <= 0.1 THEN 4
                   WHEN b2.volume_change <= 0.2 THEN 5
                   ELSE 6
               END = 
               CASE 
                   WHEN b1.volume_change <= -0.2 THEN 1
                   WHEN b1.volume_change <= -0.1 THEN 2
                   WHEN b1.volume_change <= 0 THEN 3
                   WHEN b1.volume_change <= 0.1 THEN 4
                   WHEN b1.volume_change <= 0.2 THEN 5
                   ELSE 6
               END)
          , 0.5)::NUMERIC as volume_prob,
          
          -- 技术指标因子
          COALESCE(
              CASE WHEN b1.close > b1.ma5 AND b1.ma5 > b1.ma20 THEN 1
                   WHEN b1.close < b1.ma5 AND b1.ma5 < b1.ma20 THEN 0
                   ELSE 0.5 
              END
          , 0.5)::NUMERIC as technical_prob,
          
          b1.is_up as actual_result
      FROM base_metrics b1
      WHERE b1.trade_date >= (SELECT MAX(trade_date) - INTERVAL '60 days' FROM base_metrics)
  )
  INSERT INTO factor_performance (trade_date, factor_name, prediction, actual_result, is_correct)
  SELECT 
      trade_date,
      'calendar' as factor_name,
      calendar_prob as prediction,
      actual_result,
      CASE WHEN (calendar_prob >= 0.5 AND actual_result = 1) OR
                (calendar_prob < 0.5 AND actual_result = 0)
           THEN 1 ELSE 0 
      END as is_correct
  FROM factor_predictions
  UNION ALL
  SELECT 
      trade_date,
      'streak' as factor_name,
      streak_prob as prediction,
      actual_result,
      CASE WHEN (streak_prob >= 0.5 AND actual_result = 1) OR
                (streak_prob < 0.5 AND actual_result = 0)
           THEN 1 ELSE 0 
      END as is_correct
  FROM factor_predictions
  UNION ALL
  SELECT 
      trade_date,
      'volume' as factor_name,
      volume_prob as prediction,
      actual_result,
      CASE WHEN (volume_prob >= 0.5 AND actual_result = 1) OR
                (volume_prob < 0.5 AND actual_result = 0)
           THEN 1 ELSE 0 
      END as is_correct
  FROM factor_predictions
  UNION ALL
  SELECT 
      trade_date,
      'technical' as factor_name,
      technical_prob as prediction,
      actual_result,
      CASE WHEN (technical_prob >= 0.5 AND actual_result = 1) OR
                (technical_prob < 0.5 AND actual_result = 0)
           THEN 1 ELSE 0 
      END as is_correct
  FROM factor_predictions
  ON CONFLICT (trade_date, factor_name) DO UPDATE 
  SET prediction = EXCLUDED.prediction,
      actual_result = EXCLUDED.actual_result,
      is_correct = EXCLUDED.is_correct;

  -- 计算并更新因子权重
  WITH factor_stats AS (
      SELECT 
          factor_name,
          AVG(is_correct::NUMERIC) as win_rate,
          -- 使用sigmoid函数将胜率转换为权重
          1.0 / (1.0 + EXP(-10.0 * (AVG(is_correct::NUMERIC) - 0.5))) as weight_raw
      FROM factor_performance
      WHERE trade_date >= (SELECT MAX(trade_date) - INTERVAL '30 days' FROM factor_performance)
      GROUP BY factor_name
  ),
  normalized_weights AS (
      SELECT 
          factor_name,
          win_rate,
          -- 归一化权重，使所有权重之和为1
          (weight_raw / SUM(weight_raw) OVER ())::NUMERIC as weight
      FROM factor_stats
  )
  INSERT INTO factor_weights (calculation_date, factor_name, weight, win_rate)
  SELECT 
      CURRENT_DATE,
      factor_name,
      weight,
      win_rate
  FROM normalized_weights
  ON CONFLICT (calculation_date, factor_name) DO UPDATE 
  SET weight = EXCLUDED.weight,
      win_rate = EXCLUDED.win_rate;

  -- 查看因子表现报告
  WITH recent_performance AS (
      SELECT 
          factor_name,
          COUNT(*) as total_predictions,
          (AVG(is_correct::NUMERIC) * 100)::NUMERIC(5,2) as accuracy_rate,
          (AVG(CASE WHEN prediction >= 0.5 AND actual_result = 1 THEN 1
                   WHEN prediction < 0.5 AND actual_result = 0 THEN 1
                   ELSE 0 END::NUMERIC) * 100)::NUMERIC(5,2) as directional_accuracy,
          (AVG(ABS(prediction - 0.5)) * 100)::NUMERIC(5,2) as avg_confidence,
          CORR(prediction::NUMERIC, actual_result::NUMERIC)::NUMERIC(5,4) as correlation
      FROM factor_performance
      WHERE trade_date >= (SELECT MAX(trade_date) - INTERVAL '30 days' FROM factor_performance)
      GROUP BY factor_name
  ),
  current_weights AS (
      SELECT 
          factor_name,
          (weight * 100)::NUMERIC(5,2) as weight_percentage,
          (win_rate * 100)::NUMERIC(5,2) as win_rate_percentage
      FROM factor_weights
      WHERE calculation_date = CURRENT_DATE
  )
  SELECT 
      rp.factor_name,
      rp.total_predictions,
      rp.accuracy_rate as "准确率(%)",
      rp.directional_accuracy as "方向准确率(%)",
      rp.avg_confidence as "平均置信度(%)",
      rp.correlation as "相关系数",
      cw.weight_percentage as "当前权重(%)",
      cw.win_rate_percentage as "近期胜率(%)"
  FROM recent_performance rp
  JOIN current_weights cw ON rp.factor_name = cw.factor_name
  ORDER BY cw.weight_percentage DESC;

  -- 使用最新权重进行预测
  WITH latest_metrics AS (
      SELECT *
      FROM base_metrics
      WHERE trade_date = (SELECT MAX(trade_date) FROM base_metrics)
  ),
  latest_weights AS (
      SELECT *
      FROM factor_weights
      WHERE calculation_date = CURRENT_DATE
  ),
  factor_predictions AS (
      SELECT 
          l.*,
          (
              -- 日历效应因子
              COALESCE(
                  (SELECT AVG(CASE WHEN b.is_up = 1 THEN 1.0 ELSE 0 END)
                   FROM base_metrics b
                   WHERE EXTRACT(MONTH FROM b.trade_date) = EXTRACT(MONTH FROM l.trade_date + INTERVAL '1 day')
                   AND EXTRACT(DAY FROM b.trade_date) = EXTRACT(DAY FROM l.trade_date + INTERVAL '1 day')
                   AND EXTRACT(DOW FROM b.trade_date) = EXTRACT(DOW FROM l.trade_date + INTERVAL '1 day'))
              , 0.5) * (SELECT weight FROM latest_weights WHERE factor_name = 'calendar') +
              
              -- 连续涨跌因子
              COALESCE(
                  (SELECT AVG(CASE WHEN b.is_up = 1 THEN 1.0 ELSE 0 END)
                   FROM base_metrics b
                   WHERE b.up_streak = l.up_streak)
              , 0.5) * (SELECT weight FROM latest_weights WHERE factor_name = 'streak') +
              
              -- 成交量分析因子
              COALESCE(
                  (SELECT AVG(CASE WHEN b.is_up = 1 THEN 1.0 ELSE 0 END)
                   FROM base_metrics b
                   WHERE CASE 
                       WHEN b.volume_change <= -0.2 THEN 1
                       WHEN b.volume_change <= -0.1 THEN 2
                       WHEN b.volume_change <= 0 THEN 3
                       WHEN b.volume_change <= 0.1 THEN 4
                       WHEN b.volume_change <= 0.2 THEN 5
                       ELSE 6
                   END = 
                   CASE 
                       WHEN l.volume_change <= -0.2 THEN 1
                       WHEN l.volume_change <= -0.1 THEN 2
                       WHEN l.volume_change <= 0 THEN 3
                       WHEN l.volume_change <= 0.1 THEN 4
                       WHEN l.volume_change <= 0.2 THEN 5
                       ELSE 6
                   END)
              , 0.5) * (SELECT weight FROM latest_weights WHERE factor_name = 'volume') +
              
              -- 技术指标因子
              COALESCE(
                  CASE WHEN l.close > l.ma5 AND l.ma5 > l.ma20 THEN 1
                       WHEN l.close < l.ma5 AND l.ma5 < l.ma20 THEN 0
                       ELSE 0.5 
                  END
              , 0.5) * (SELECT weight FROM latest_weights WHERE factor_name = 'technical')
          )::NUMERIC(5,4) as weighted_probability
      FROM latest_metrics l
  )
  SELECT 
      (SELECT MAX(trade_date) + INTERVAL '1 day' FROM base_metrics) as prediction_date,
      (weighted_probability * 100)::NUMERIC(5,2) as next_day_up_probability,
      CASE 
          WHEN weighted_probability >= 0.7 THEN '强买入信号'
          WHEN weighted_probability >= 0.6 THEN '买入信号'
          WHEN weighted_probability >= 0.5 THEN '弱买入信号'
          WHEN weighted_probability >= 0.4 THEN '弱卖出信号'
          WHEN weighted_probability >= 0.3 THEN '卖出信号'
          ELSE '强卖出信号'
      END as signal
  FROM factor_predictions;


  CREATE OR REPLACE FUNCTION public.get_price_patterns(
	)
    RETURNS TABLE(week_period character varying, pattern character varying, cases bigint, avg_next_return numeric, next_day_win_rate numeric, avg_current_return numeric, avg_movement numeric) 
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE PARALLEL UNSAFE
    ROWS 1000

AS $BODY$
BEGIN
    RETURN QUERY 
	
	WITH daily_returns AS (
    SELECT 
        trade_date,
        a.week_period,
        close,
        close / LAG(close) OVER (ORDER BY trade_date) - 1 as daily_return
    FROM crypto_prices a
),
consecutive_pattern AS (
    SELECT 
        trade_date,
        a.week_period,
        daily_return,
        LAG(daily_return) OVER (ORDER BY trade_date) as prev_day_return,
        LEAD(daily_return) OVER (ORDER BY trade_date) as next_day_return
    FROM daily_returns a
)
SELECT 
    a.week_period,
    CASE 
        WHEN prev_day_return > 0 AND daily_return > 0 THEN '连续上涨'
        WHEN prev_day_return < 0 AND daily_return < 0 THEN '连续下跌'
        WHEN prev_day_return < 0 AND daily_return > 0 THEN '先跌后涨'
        ELSE '先涨后跌'
    END::VARCHAR(20) as pattern,
    COUNT(*) as cases,
    ROUND((AVG(next_day_return) * 100)::numeric, 2) as avg_next_return,
    ROUND((COUNT(CASE WHEN next_day_return > 0 THEN 1 END) * 100.0 / COUNT(*))::numeric, 2) as next_day_win_rate,
    -- 添加平均涨跌幅度
    ROUND((AVG(daily_return) * 100)::numeric, 2) as avg_current_return,
    ROUND((AVG(ABS(daily_return)) * 100)::numeric, 2) as avg_movement
FROM consecutive_pattern a
WHERE 
    prev_day_return IS NOT NULL 
    AND next_day_return IS NOT NULL
GROUP BY 1, 2
ORDER BY 
    a.week_period ,
    pattern;
END;
$BODY$;

-- Table: public.price_patterns

-- DROP TABLE IF EXISTS public.price_patterns;

CREATE TABLE IF NOT EXISTS public.price_patterns
(
    id integer NOT NULL DEFAULT nextval('price_patterns_id_seq'::regclass),
    week_period text COLLATE pg_catalog."default" NOT NULL,
    pattern text COLLATE pg_catalog."default" NOT NULL,
    cases integer NOT NULL,
    avg_next_return numeric(8,4) NOT NULL,
    next_day_win_rate numeric(8,4) NOT NULL,
    avg_current_return numeric(8,4) NOT NULL,
    avg_movement numeric(8,4) NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    CONSTRAINT price_patterns_pkey PRIMARY KEY (id),
    CONSTRAINT price_patterns_week_period_pattern_key UNIQUE (week_period, pattern)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.price_patterns
    OWNER to postgres;


    
CREATE TABLE IF NOT EXISTS public.kline_data
(
    id integer NOT NULL DEFAULT nextval('kline_data_id_seq'::regclass),
    "timestamp" timestamp with time zone,
    open_price numeric(20,8),
    high_price numeric(20,8),
    low_price numeric(20,8),
    close_price numeric(20,8),
    volume numeric(20,8),
    volume_currency numeric(20,8),
    volume_currency_quote numeric(20,8),
    is_confirmed boolean,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    symbol character varying(20) COLLATE pg_catalog."default",
    CONSTRAINT kline_data_pkey PRIMARY KEY (id),
    CONSTRAINT unique_key UNIQUE (symbol, "timestamp")
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.kline_data
    OWNER to postgres;
-- Index: idx_kline_timestamp

-- DROP INDEX IF EXISTS public.idx_kline_timestamp;

CREATE INDEX IF NOT EXISTS idx_kline_timestamp
    ON public.kline_data USING btree
    ("timestamp" ASC NULLS LAST)
    TABLESPACE pg_default;


CREATE TABLE IF NOT EXISTS public.active_positions
(
    id integer NOT NULL DEFAULT nextval('active_positions_id_seq'::regclass),
    direction character varying(10) COLLATE pg_catalog."default" NOT NULL,
    entry_price numeric(20,8) NOT NULL,
    size numeric(20,8) NOT NULL,
    stop_loss numeric(20,8) NOT NULL,
    take_profit numeric(20,8) NOT NULL,
    entry_time timestamp without time zone NOT NULL,
    pattern character varying(50) COLLATE pg_catalog."default",
    day_of_week character varying(20) COLLATE pg_catalog."default",
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now(),
    CONSTRAINT active_positions_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.active_positions
    OWNER to postgres;

ALTER TABLE crypto_prices
ADD COLUMN date_period VARCHAR(10) 
GENERATED ALWAYS AS (
    CASE 
        WHEN EXTRACT(MONTH FROM trade_date) = 1 AND EXTRACT(DAY FROM trade_date) <= 3 THEN '年初'
        WHEN EXTRACT(MONTH FROM trade_date) = 12 AND EXTRACT(DAY FROM trade_date) >= 28 THEN '年末'
        WHEN EXTRACT(MONTH FROM trade_date) IN (1,4,7,10) AND EXTRACT(DAY FROM trade_date) <= 3 THEN '季初'
        WHEN EXTRACT(MONTH FROM trade_date) IN (3,6,9,12) AND EXTRACT(DAY FROM trade_date) >= 28 THEN '季末'
        WHEN EXTRACT(DAY FROM trade_date) <= 3 THEN '月初'
        WHEN EXTRACT(DAY FROM trade_date) >= 28 THEN '月末'
		ELSE '其他'
    END
) STORED;