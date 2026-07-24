package validator

// Validates credit card formats:
// using the Luhn Algorithm, checks expiration dates,
// and validates shipping address formatting without making any network calls.

import (
	"errors"
	"fmt"
	"regexp"
	"strconv"
	"strings"
	"time"

	pb "github.com/open-telemetry/techx-corp/src/checkout/genproto/oteldemo"
)

var (
	ErrInvalidCardNumber = errors.New("invalid credit card number (must 13-19 digits and pass Luhn check)")
	ErrInvalidCVV        = errors.New("invalid CVV (must be 3 or 4 digits)")
	ErrCardExpired       = errors.New("credit card has expired")
	ErrInvalidAddress    = errors.New("shipping address fields are incomplete or invalid")
)

var (
	zipRegex  = regexp.MustCompile(`^[A-Za-z0-9\s\-]{3,10}$`)
	digitOnly = regexp.MustCompile(`^\d+$`)
)

// Performs in-memory syntax and mathematical checks on CreditCardInfo
func ValidateCreditCard(card *pb.CreditCardInfo) error {
	if card == nil {
		return errors.New("credit card information is missing")
	}

	// 1. Sanitize and check length (13 to 19 digits)
	cleanNum := strings.ReplaceAll(card.CreditCardNumber, "-", "")
	cleanNum = strings.ReplaceAll(cleanNum, " ", "")

	if len(cleanNum) < 13 || len(cleanNum) > 19 || !digitOnly.MatchString(cleanNum) {
		return ErrInvalidCardNumber
	}

	// 2. Validate via Luhn Algorithm
	if !passesLuhnCheck(cleanNum) {
		return ErrInvalidCardNumber
	}

	// 3. Validate CVV (3 or 4 digits)
	cvvStr := strconv.Itoa(int(card.CreditCardCvv))
	if len(cvvStr) < 3 || len(cvvStr) > 4 {
		return ErrInvalidCVV
	}

	// 4. Validate Expiration Date 
	now := time.Now()
	currentYear := now.Year()
	currentMonth := now.Month()

	expYear := int(card.CreditCardExpirationYear)
	expMonth := int(card.CreditCardExpirationMonth)

	if expMonth < 1 || expMonth > 12 {
		return errors.New("invalid expiration month")
	}

	if expYear < currentYear || (expYear == currentYear && expMonth < int(currentMonth)) {
		return ErrCardExpired
	}

	return nil
}

// ValidateAddress checks all mandatory address fields are populated and valid 
func ValidateAddress(addr *pb.Address) error {
	if addr == nil {
		return ErrInvalidAddress
	}

	if strings.TrimSpace(addr.StreetAddress) == "" {
		return fmt.Errorf("%w: street address is required", ErrInvalidAddress)
	}

	if strings.TrimSpace(addr.City) == "" {
		return fmt.Errorf("%w: city is required", ErrInvalidAddress)
	}

	if strings.TrimSpace(addr.Country) == "" {
		return fmt.Errorf("%w: country is required", ErrInvalidAddress)
	}

	zip := strings.TrimSpace(addr.ZipCode)
	if zip == "" || !zipRegex.MatchString(zip) {
		return fmt.Errorf("%w: invalid postal/zip code format", ErrInvalidAddress)
	}
	
	return nil
}

// passesLuhnCheck implements the Luhn Algorithm (Mod 10) for credit card validation.
func passesLuhnCheck(cardNumber string) bool {
	var sum int 
	alternate := false 

	for i := len(cardNumber) - 1; i >= 0; i-- {
		n, err := strconv.Atoi(string(cardNumber[i]))

		if err != nil {
			return false
		}

		if alternate {
			n *= 2
			if n > 9 {
				n -= 9
			}
		}

		sum += n 
		alternate = !alternate
	}

	return sum%10 == 0
}