// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const { context, propagation, trace, metrics } = require('@opentelemetry/api');
const cardValidator = require('simple-card-validator');
const { v4: uuidv4 } = require('uuid');

const { OpenFeature } = require('@openfeature/server-sdk');
const { FlagdProvider } = require('@openfeature/flagd-provider');
const flagProvider = new FlagdProvider();

const logger = require('./logger');
const tracer = trace.getTracer('payment');
const meter = metrics.getMeter('payment');
const transactionsCounter = meter.createCounter('app.payment.transactions');

const LOYALTY_LEVEL = ['platinum', 'gold', 'silver', 'bronze'];

//! Microservice best practice dictates that 
//! a service should never blindly trust incoming messages from external event buses or upstream callers. 
//! That's why I include some checkout validation checks here

//! PCI-DSS Compliance: Raw 16-digit credit card numbers are not exposed on Kafka topics
module.exports.chargeWithToken = async ({ paymentToken, amount, orderId, cardType, lastFourDigits}) => {
  const span = tracer.startSpan('chargeWithToken');
  
  span.setAttributes({
		"app.payment.order_id": orderId || "",
		"app.payment.token": paymentToken || "",
		"app.payment.card_type": cardType || "",
  });
  
  // 1. Zero-Trust Check: Ensure mandatory parameters exist                                                                                                                  
  if (!orderId || !paymentToken) {                                                                                                                                           
    span.setStatus({ code: SpanStatusCode.ERROR, message: 'Missing mandatory orderId or paymentToken' });                                                                    
    span.end();                                                                                                                                                              
    throw new Error(`Defensive check failed: orderId (${orderId}) or paymentToken missing.`);                                                                                
  }
  
  // 2. Security Check: Validate payment token format                                                                                                                        
  if (!paymentToken.startsWith('tok_')) {                                                                                                                                    
    span.setStatus({ code: SpanStatusCode.ERROR, message: 'Invalid payment token signature' });                                                                              
    span.end();                                                                                                                                                              
    throw new Error(`Defensive check failed: Invalid payment token format '${paymentToken}'`);                                                                               
  }

  // 3. Financial Integrity Check: Ensure non-negative amounts & valid currency
  const units = amount?.units || 0;
  const nanos = amount?.nanos || 0;
  const currencyCode = amount?.currencyCode || 'USD';
  if (units < 0 || nanos < 0) {
		span.setStatus({
			code: SpanStatusCode.ERROR,
			message: "Negative payment amount rejected",
		});
		span.end();
		throw new Error(
			`Defensive check failed: Invalid negative amount units=${units}, nanos=${nanos}`,
		);
  }
  
  // 4. Policy Check: Ensure card network compliance                                                                                                                         
  if (cardType && !['visa', 'mastercard'].includes(cardType.toLowerCase())) {                                                                                                
    span.setStatus({ code: SpanStatusCode.ERROR, message: 'Unsupported credit card network' });                                                                              
    span.end();                                                                                                                                                              
    throw new Error(`Defensive check failed: Unsupported card network '${cardType}'`);                                                                                       
  }
  
  const transactionId = uuidv4();
  logger.info(
		{
			transactionId,
			orderId,
			paymentToken,
			amount: { units, nanos, currencyCode },
		},
		"Token charge transaction complete.",
  );

  transactionsCounter.add(1, { 'app.payment.currency': currencyCode });
  span.end();

  return { transactionId };
}