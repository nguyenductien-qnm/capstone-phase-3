CREATE SCHEMA  IF NOT EXISTS checkout;

-- Write-optimized with JSONB data format
CREAT TABLE checkout.orders (
	order_id TEXT PRIMARY KEY,
	user_id TEXT NOT NULL,
	total_amount_units BIGINIT NOT NULL,
	total_amount_nanos INT NOT NULL,
	currency_code TEXT NOT NULL DEFAULT 'USD',
	status TEXT NOT NULL DEFAULT 'PENDING',

	order_metadata JSONB NOT NULL,

	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
)

CREATE TABLE checkout.outbox (
	id BIGSERIAL PRIMARY KEY,
	aggregate_type TEXT NOT NULL DEFAULT 'Order',
	aggregate_id TEXT NOT NULL, 
	event_type TEXT NOT NULL,

	payload JSONB NOT NULL,

	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
)

