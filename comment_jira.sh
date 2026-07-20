#!/bin/bash
JIRA_CFG=$(cat ~/.claude.json | jq -c '.. | .jira? | select(. != null and .env != null)')
JIRA_URL=$(echo $JIRA_CFG | jq -r '.env.JIRA_URL')
JIRA_USER=$(echo $JIRA_CFG | jq -r '.env.JIRA_USERNAME')
JIRA_TOKEN=$(echo $JIRA_CFG | jq -r '.env.JIRA_API_TOKEN')

cat << 'JSON' > payload.json
{
  "body": {
    "version": 1,
    "type": "doc",
    "content": [
      {
        "type": "paragraph",
        "content": [
          {
            "type": "text",
            "text": "Cập nhật hoàn thành Mandate 06.\n\nTình trạng: Hoàn thành.\nTài liệu, ảnh chụp màn hình UI và test log đã được thêm vào thư mục docs/ai/evals/ của Repo. Đã cập nhật MANDATE_06_EVIDENCE.md khớp với mandate.\n\nLưu ý: Tiến độ mandate này có trễ vì chưa quản lý tốt task và các thành viên, dẫn đến việc tôi phải đích thân fix một số PRs (bao gồm PR #185) để mandate hoàn thành đúng hạn.\n"
          }
        ]
      }
    ]
  }
}
JSON

curl -s -X POST -u "$JIRA_USER:$JIRA_TOKEN" \
  -H "Content-Type: application/json" \
  -d @payload.json \
  "$JIRA_URL/rest/api/3/issue/TF1-83/comment"
