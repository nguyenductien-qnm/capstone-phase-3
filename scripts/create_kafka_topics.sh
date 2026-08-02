#!/usr/bin/env bash
# ==============================================================================
# Description: Creates Kafka topics in MSK using credentials from K8s msk-secret (SASL/SCRAM authentication)
# Topics: domain.checkout.payment, domain.checkout.shipping
# ==============================================================================
set -euo pipefail 

NAMESPACE="${NAMESPACE:-techx-develop}"
TOPICS=("domain.checkout.payment" "domain.checkout.shipping")
PARTITIONS=3
REPLICATION_FACTOR=2

echo "Extracting MSK credentials from secret 'msk-secret' in namespace '${NAMESPACE}' ... "
BROKER=$(kubectl get secret msk-secret -n ${NAMESPACE} -o jsonpath='{.data.endpoint}' | base64 -d)
USERNAME=$(kubectl get secret msk-secret -n ${NAMESPACE} -o jsonpath='{.data.username}' | base64 -d)
PASSWORD=$(kubectl get secret msk-secret -n ${NAMESPACE} -o jsonpath='{.data.password}' | base64 -d)

CREATE_CMDS=""
for TOPIC in "${TOPICS[@]}"; do
	CREATE_CMDS+="
		echo 'Creating topic ${TOPIC} ... '
		kafka-topics.sh --bootstrap-server \"${BROKER}\" \\
			--create \\
			--if-not-exists \\
			--topic '${TOPIC}' \\
			--partitions ${PARTITIONS} \\
			--replication-factor ${REPLICATION_FACTOR} \\
			--command-config /tmp/client.properties
	"
done 

# Run ephemeral pod with Kafka CLI to execute topic creation
kubectl run kafka-topic-creator -n "${NAMESPACE}" --rm -i --tty \
	--image=bitnami/kafka:3.9.0 -- bash -c "
		
		# Create client.properties for SASL/SCRAM authentication
		cat <<EOF > /tmp/client.properties
		security.protocol=SASL_SSL
		sasl.mechanism=SCRAM-SHA-512
		sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username=\"${USERNAME}\" password=\"${PASSWORD}\";
		EOF 

		${CREATE_CMDS}

		echo '--- Existing topics on MSK ---'
		kafka-topics.sh --bootstrap-server "${BROKER}" --list --command-config /tmp/client.properties
	"
