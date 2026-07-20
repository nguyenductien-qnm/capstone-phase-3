import json

with open('jira_response.json') as f:
    data = json.load(f)

def adf_to_text(node):
    if type(node) is str:
        return node
    text = ""
    if isinstance(node, dict):
        if node.get('type') == 'text':
            return node.get('text', '')
        content = node.get('content', [])
        for c in content:
            text += adf_to_text(c)
        if node.get('type') == 'paragraph':
            text += '\n\n'
        elif node.get('type') == 'heading':
            text = '#' * node.get('attrs', {}).get('level', 1) + ' ' + text + '\n\n'
        elif node.get('type') == 'listItem':
            text = '- ' + text + '\n'
        elif node.get('type') == 'bulletList' or node.get('type') == 'orderedList':
            text += '\n'
    elif isinstance(node, list):
        for c in node:
            text += adf_to_text(c)
    return text

description = adf_to_text(data['fields']['description'])
with open('jira_desc.md', 'w') as f:
    f.write(description)
