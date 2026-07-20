package main

import (
	"fmt"
    "context"
	"encoding/json"

    "github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
	"github.com/google/uuid"

	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
)

// If an order get PENDING_PAYMENT / PENDING_SHIPPING
// we store reqPayload in addition which contains formatted credit card info
// so, Lambda can later use this info to re-execute payment/shipping operation
func (cs *checkout) putOrderState(
    ctx context.Context,
    orderID uuid.UUID,
    orderStatus string,
    shippingStatus string,
    paymentStatus string,
    reconcilePK string, 
    reconcileAt string,
    reqPayload *pb.PlaceOrderRequest,
    orderResult *pb.OrderResult,
) error {
    item := map[string]types.AttributeValue{
        "order_id": &types.AttributeValueMemberS{Value: orderID.String()},
        "order_status": &types.AttributeValueMemberS{Value: orderStatus},
        "payment_status": &types.AttributeValueMemberS{Value: paymentStatus},
        "shipping_status": &types.AttributeValueMemberS{Value: shippingStatus},

        "reconcile_pk": &types.AttributeValueMemberS{Value: reconcilePK},
        "reconcile_at": &types.AttributeValueMemberS{Value: reconcileAt},
    }

    // Original payload request
    if reqPayload != nil{
        reqBytes, _ := json.Marshal(reqPayload)
        item["retry_payload"] = &types.AttributeValueMemberS{Value: string(reqBytes)}
    }

    // Completed order payload
    if orderResult != nil{
        dataBytes, _ := json.Marshal(orderResult)
        item["order_data"] = &types.AttributeValueMemberS{Value: string(dataBytes)}
    }

    _, err := cs.dynamoClient.PutItem(ctx, &dynamodb.PutItemInput{
        TableName: aws.String(cs.tableName),
        Item: item,
    })
    if err != nil{
        logger.Error(fmt.Sprintf("Failed to put item to DynamoDB: %v", err))
    }

    return err
}