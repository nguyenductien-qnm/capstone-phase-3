package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestFetchContainerAWSCredentials(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "pod-token" {
			t.Fatalf("authorization header = %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"AccessKeyId":"AKIA","SecretAccessKey":"secret","Token":"session"}`))
	}))
	defer server.Close()

	ak, sk, token, err := fetchContainerAWSCredentials(context.Background(), server.Client(), server.URL, "pod-token")
	if err != nil {
		t.Fatal(err)
	}
	if ak != "AKIA" || sk != "secret" || token != "session" {
		t.Fatalf("credentials = %q/%q/%q", ak, sk, token)
	}
}
