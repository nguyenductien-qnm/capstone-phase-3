import json

with open('jira_response.json') as f:
    data = json.load(f)

desc = data['fields']['description']

def update_node(node):
    if isinstance(node, dict):
        if node.get('type') == 'text':
            if node['text'] == 'Copilot confirmation gate + injection eval: TF1-74 (In Progress)':
                node['text'] = 'Copilot confirmation gate + injection eval: TF1-74 (Done)'
            elif node['text'] == 'Eval fidelity + injection: python docs/ai/evals/run_evals.py voi golden_qa_dataset.json (24 case: grounded/no_info/injection) + golden_dataset.json (10 case summary)':
                node['text'] = 'Eval fidelity + injection: python3 docs/ai/evals/eval_mandate06_v5.py --mode offline (25 case: pass 100%)'
            elif '(c) Eval chay ra so - bao cao trong 04_eval_report.md' in node['text']:
                node['text'] = node['text'].replace('04_eval_report.md', 'MANDATE_06_EVIDENCE.md (Pass 25/25 case)')
            elif 'Dinh Nguyen (review)' in node['text']:
                node['text'] = node['text'].replace('Dinh Nguyen (review)', 'Dinh Nguyen (review & hotfix PR #178-185 phut chot do delay)')
        if 'content' in node:
            for child in node['content']:
                update_node(child)
    elif isinstance(node, list):
        for child in node:
            update_node(child)

update_node(desc)

# Find the "Link PR/commit" list to append the new PRs
for i, block in enumerate(desc['content']):
    if block.get('type') == 'heading' and len(block.get('content', [])) > 0:
        if 'Link PR/commit' in block['content'][0].get('text', ''):
            list_block = desc['content'][i+1]
            if list_block.get('type') == 'bulletList':
                list_block['content'].append({"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Copilot fallback, region & routing loop fixes: PR #182, #181, #179, #178"}]}]})
                list_block['content'].append({"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Ask-AI bypass grounding & eval fixes (hotfix by Dinh): PR #185"}]}]})
        elif 'Bang chung chay that' in block['content'][0].get('text', ''):
            list_block = desc['content'][i+1]
            if list_block.get('type') == 'bulletList':
                list_block['content'].append({"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "(e) UI Screenshots va test scripts luu tai thu muc docs/ai/evals/images/"}]}]})

desc['content'].append({
    "type": "panel",
    "attrs": {"panelType": "warning"},
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "LƯU Ý VỀ TIẾN ĐỘ: Tiến độ Mandate 06 trễ so với dự kiến. Nguyên nhân do chưa quản lý tốt task và các thành viên trong team, dẫn đến việc Dinh Nguyen phải đích thân can thiệp và trực tiếp fix lượng lớn lỗi vào phút chót (thông qua PR #178 đến #185) để pass 100% eval test."}]}
    ]
})

payload = {"fields": {"description": desc}}
with open('jira_update_payload.json', 'w') as f:
    json.dump(payload, f)
