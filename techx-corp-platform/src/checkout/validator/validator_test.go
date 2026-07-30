package validator

import (
	"testing"
	"time"

	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
)

func TestValidateCreditCard(t * testing.T)  {
	currentYear := int32(time.Now().Year())

	tests := []struct {
		name string
		card *pb.CreditCardInfo
		wantErr bool
	}{
		{
			name: "Valid Visa Card",
			card: &pb.CreditCardInfo{
				CreditCardNumber:          "4532015112830366", // Valid Luhn card                                                                                     
	            CreditCardCvv:             123,                                                                                                                       
	            CreditCardExpirationYear:  currentYear + 2,                                                                                                           
	            CreditCardExpirationMonth: 12,
			},
		wantErr: false,	
	},
	{
		name: "Invalid Luhn Checksum",
		card: &pb.CreditCardInfo{
			CreditCardNumber:          "4532015112830366",                                                                                                        
            CreditCardCvv:             123,                                                                                                                       
            CreditCardExpirationYear:  2020,                                                                                                                      
            CreditCardExpirationMonth: 1,
		},
		wantErr: true,
	},
}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateCreditCard(tt.card)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateCreditCard() error = %v, wantErro %v", err, tt.wantErr)
			}
		})
	}
}