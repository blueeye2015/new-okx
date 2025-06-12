-- Create a view to calculate strategy statistics
CREATE OR REPLACE VIEW strategy_stats AS
WITH trade_stats AS (
    SELECT 
        strategy_name,
        COUNT(*) FILTER (WHERE trade_executed = true) as total_executed_trades,
        COUNT(*) FILTER (WHERE trade_result = 'win') as total_wins,
        COUNT(*) FILTER (WHERE trade_result = 'loss') as total_losses,
        AVG(CASE WHEN trade_result = 'win' THEN profit_pct ELSE NULL END) as avg_win_pct,
        AVG(CASE WHEN trade_result = 'loss' THEN profit_pct ELSE NULL END) as avg_loss_pct,
        AVG(confidence_score) as avg_confidence
    FROM strategy_performance
    WHERE trade_executed = true 
    AND trade_result IN ('win', 'loss')
    GROUP BY strategy_name
)
SELECT 
    strategy_name,
    total_executed_trades,
    total_wins,
    total_losses,
    ROUND(CAST(total_wins AS DECIMAL) / NULLIF(total_executed_trades, 0) * 100, 2) as win_rate_pct,
    avg_win_pct,
    avg_loss_pct,
    avg_confidence,
    NOW() as last_updated
FROM trade_stats;

-- Create an index on strategy_performance to optimize the view
CREATE INDEX idx_strategy_performance_strategy_result 
ON strategy_performance(strategy_name, trade_executed, trade_result); 