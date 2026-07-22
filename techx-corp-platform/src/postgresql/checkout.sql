CREATE SCHEMA IF NOT EXISTS checkout;

-- Write-optimized with JSONB data format
CREATE TABLE checkout.orders (
	order_id TEXT PRIMARY KEY,
	user_id TEXT NOT NULL,
	currency_code TEXT NOT NULL DEFAULT 'USD',
	status TEXT NOT NULL DEFAULT 'PROCESSING',

	-- user credentials are included here	
	order_metadata JSONB NOT NULL,

	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Control which fields downstream services can consume
CREATE TABLE checkout.outbox (
	id BIGSERIAL PRIMARY KEY, -- Auto-increment
	aggregate_type TEXT NOT NULL DEFAULT 'Order',
	aggregate_id TEXT NOT NULL, -- order_id
	event_type TEXT NOT NULL, -- 'ORDER_PLACED', 'ORDER_COMPLETED'

	payload JSONB NOT NULL,

	created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

