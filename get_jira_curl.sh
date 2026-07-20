#!/bin/bash
JIRA_CFG=$(cat ~/.claude.json | jq -c '.. | .jira? | select(. != null and .env != null)')
JIRA_URL=$(echo $JIRA_CFG | jq -r '.env.JIRA_URL')
JIRA_USER=$(echo $JIRA_CFG | jq -r '.env.JIRA_USERNAME')
JIRA_TOKEN=$(echo $JIRA_CFG | jq -r '.env.JIRA_API_TOKEN')

curl -s -u "$JIRA_USER:$JIRA_TOKEN" -H "Content-Type: application/json" "$JIRA_URL/rest/api/3/issue/TF1-83" > jira_response.json

echo "Summary: $(jq -r '.fields.summary' jira_response.json)"
echo "Status: $(jq -r '.fields.status.name' jira_response.json)"
echo "Description: $(jq -r '.fields.description' jira_response.json | head -n 20)"
