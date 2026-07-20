#!/bin/bash
JIRA_CFG=$(cat ~/.claude.json | jq -c '.. | .jira? | select(. != null and .env != null)')
JIRA_URL=$(echo $JIRA_CFG | jq -r '.env.JIRA_URL')
JIRA_USER=$(echo $JIRA_CFG | jq -r '.env.JIRA_USERNAME')
JIRA_TOKEN=$(echo $JIRA_CFG | jq -r '.env.JIRA_API_TOKEN')

curl -s -u "$JIRA_USER:$JIRA_TOKEN" "$JIRA_URL/rest/api/3/issue/TF1-83/transitions" > transitions.json
jq '.transitions[] | {id, name}' transitions.json
