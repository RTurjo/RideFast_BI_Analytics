# Data dictionary

Synthetic ride-hailing data for the fictional company **RideFast** (12 cities). Ride requests cover 1 Jul 2023 – 29 Jun 2024.

## rides.csv — fact table (120,000 rows)
| Column | Type | Description |
|---|---|---|
| ride_id | string | Primary key |
| user_id | string | FK → users |
| driver_id | string | FK → drivers |
| city | string | One of 12 operating cities |
| pickup_zone | string | Sub-city zone (e.g. `NOR-Z04`) |
| request_time | datetime | When the ride was requested |
| pickup_time | datetime | When the driver arrived |
| dropoff_time | datetime | Ride end (blank if not completed) |
| status | string | `completed` · `cancelled_driver` · `cancelled_user` · `no_show` |
| fare_amount | float | Final fare in USD (0 if not completed) |
| surge_multiplier | float | 1.0 = no surge |
| promo_code_used | bool | Promo applied |
| promo_discount | float | Discount in USD |
| rating_by_user / rating_by_driver | float | 1–5, blank if not completed |
| vehicle_type | string | `economy` · `comfort` · `xl` |
| distance_km | float | Trip distance |
| payment_method | string | `card` · `wallet` · `cash` |

## drivers.csv (8,000 rows)
`driver_id`, `city`, `signup_date`, `vehicle_type`, `status` (active / suspended / churned), `avg_rating`, `total_rides`, `acceptance_rate` (0–1), `cancellation_rate` (0–1), `online_hours_monthly`

## users.csv (35,000 rows)
`user_id`, `signup_date`, `city`, `total_rides`, `last_ride_date`, `promo_rides`, `wallet_balance`, `churn_flag` (True = no ride in the past 60 days)

## support_tickets.csv (22,000 rows)
`ticket_id`, `ride_id` (blank if not ride-related), `user_id`, `driver_id`, `created_at`, `category` (fare_dispute / safety / lost_item / app_issue / driver_behaviour), `severity` (low → critical), `resolved`, `resolution_time_hours`

## Engineered fields (`processed/rides_enriched.csv`, created by `src/pipeline.py`)
| Field | Logic |
|---|---|
| wait_min | pickup_time − request_time, minutes |
| trip_min | dropoff_time − pickup_time, minutes |
| is_completed / is_driver_cancel | 1/0 flags from status |
| request_month / request_hour / request_weekday | from request_time |
| wait_bucket | 0-5, 5-10, 10-15, 15-20, 20+ min |
| gross_fare | fare_amount + promo_discount (completed rides) |
