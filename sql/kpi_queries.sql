-- =============================================================================
-- RideFast BI Analysis - KPI queries
-- Tables: rides, drivers, users, support_tickets  (loaded 1:1 from data/raw/*.csv)
-- Dialect: ANSI-style SQL, tested on SQLite. For BigQuery / PostgreSQL swap the
-- time-difference expression (see comment in Q2).
-- =============================================================================


-- Q1. Headline funnel: how many requests become completed rides?
SELECT
    COUNT(*)                                                        AS ride_requests,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)           AS completed_rides,
    ROUND(AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0 END), 4)        AS completion_rate,
    ROUND(AVG(CASE WHEN status = 'cancelled_driver' THEN 1.0 ELSE 0 END), 4) AS driver_cancel_rate,
    ROUND(SUM(CASE WHEN status = 'completed' THEN fare_amount ELSE 0 END), 2) AS completed_revenue
FROM rides;


-- Q2. City scorecard: completion, driver cancellation, wait time, rating
--     wait time in minutes. BigQuery: TIMESTAMP_DIFF(pickup_time, request_time, MINUTE)
--                           Postgres: EXTRACT(EPOCH FROM pickup_time - request_time)/60
SELECT
    city,
    COUNT(*)                                                                  AS requests,
    ROUND(AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0 END), 4)        AS completion_rate,
    ROUND(AVG(CASE WHEN status = 'cancelled_driver' THEN 1.0 ELSE 0 END), 4) AS driver_cancel_rate,
    ROUND(AVG((julianday(pickup_time) - julianday(request_time)) * 1440), 2) AS avg_wait_min,
    ROUND(AVG(rating_by_user), 2)                                             AS avg_user_rating
FROM rides
GROUP BY city
ORDER BY completion_rate;


-- Q3. Zone drill-down: worst pickup zones vs the network average
WITH zone_kpi AS (
    SELECT
        city,
        pickup_zone,
        COUNT(*) AS requests,
        AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0 END)        AS completion_rate,
        AVG((julianday(pickup_time) - julianday(request_time)) * 1440) AS avg_wait_min
    FROM rides
    GROUP BY city, pickup_zone
),
network AS (
    SELECT AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0 END) AS network_rate FROM rides
)
SELECT
    z.city,
    z.pickup_zone,
    z.requests,
    ROUND(z.completion_rate, 4)                    AS completion_rate,
    ROUND(z.completion_rate - n.network_rate, 4)   AS gap_vs_network,
    ROUND(z.avg_wait_min, 1)                       AS avg_wait_min,
    -- rides lost vs network average = revenue opportunity
    ROUND((n.network_rate - z.completion_rate) * z.requests, 0) AS rides_below_network
FROM zone_kpi z CROSS JOIN network n
ORDER BY z.completion_rate
LIMIT 10;


-- Q4. Wait-time buckets: does waiting drive failure?
SELECT
    CASE
        WHEN w < 5  THEN '1) 0-5 min'
        WHEN w < 10 THEN '2) 5-10 min'
        WHEN w < 15 THEN '3) 10-15 min'
        WHEN w < 20 THEN '4) 15-20 min'
        ELSE             '5) 20+ min'
    END AS wait_bucket,
    COUNT(*) AS requests,
    ROUND(AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0 END), 4)        AS completion_rate,
    ROUND(AVG(CASE WHEN status = 'cancelled_driver' THEN 1.0 ELSE 0 END), 4) AS driver_cancel_rate
FROM (
    SELECT *, ROUND((julianday(pickup_time) - julianday(request_time)) * 1440, 2) AS w FROM rides
) t
GROUP BY wait_bucket
ORDER BY wait_bucket;


-- Q5. Promotion effectiveness: completion and fare, promo vs non-promo
SELECT
    promo_code_used,
    COUNT(*)                                                           AS requests,
    ROUND(AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0 END), 4) AS completion_rate,
    ROUND(AVG(CASE WHEN status = 'completed' THEN fare_amount END), 2) AS avg_completed_fare,
    ROUND(AVG(promo_discount), 2)                                      AS avg_discount,
    ROUND(SUM(promo_discount), 2)                                      AS total_discount
FROM rides
GROUP BY promo_code_used;


-- Q6. User retention: active vs churned profile
SELECT
    CASE WHEN churn_flag = 'True' THEN 'Churned' ELSE 'Active' END AS segment,
    COUNT(*)                         AS users,
    ROUND(AVG(total_rides), 1)       AS avg_lifetime_rides,
    ROUND(AVG(promo_rides), 1)       AS avg_promo_rides,
    ROUND(AVG(wallet_balance), 2)    AS avg_wallet_balance
FROM users
GROUP BY segment;


-- Q7. Support quality: volume, unresolved share and resolution time by category
SELECT
    category,
    COUNT(*)                                                         AS tickets,
    ROUND(AVG(CASE WHEN resolved = 'True' THEN 0.0 ELSE 1 END), 4)  AS unresolved_rate,
    ROUND(AVG(resolution_time_hours), 2)                             AS avg_resolution_hrs,
    SUM(CASE WHEN severity IN ('high', 'critical') THEN 1 ELSE 0 END) AS high_or_critical
FROM support_tickets
GROUP BY category
ORDER BY tickets DESC;


-- Q8. Driver supply health by city (joins driver attributes to ride outcomes)
SELECT
    d.city,
    COUNT(DISTINCT d.driver_id)                                       AS drivers,
    ROUND(AVG(d.acceptance_rate), 3)                                  AS avg_acceptance_rate,
    ROUND(AVG(d.cancellation_rate), 3)                                AS avg_driver_cancel_rate,
    ROUND(AVG(d.online_hours_monthly), 1)                             AS avg_online_hours,
    ROUND(AVG(CASE WHEN d.status = 'active' THEN 1.0 ELSE 0 END), 3) AS active_share
FROM drivers d
GROUP BY d.city
ORDER BY avg_driver_cancel_rate DESC;
