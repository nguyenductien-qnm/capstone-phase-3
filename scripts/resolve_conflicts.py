import re

values_path = r"C:\Users\THANH TRUNG\Desktop\Phase3\capstone-phase-3\platform\charts\application\values.yaml"

def resolve_conflicts():
    with open(values_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # The merge conflict pattern looks like:
    # <<<<<<< HEAD
    # [local changes]
    # =======
    # [remote changes]
    # >>>>>>> 15dcacf...
    
    # We want to replace this entire block with just the [remote changes] block,
    # because the remote changes contain the correct sizing for CDO-42 HPA.
    conflict_pattern = r"<<<<<<< HEAD\n([\s\S]*?)\n=======\n([\s\S]*?)\n>>>>>>> [a-f0-9]+"
    
    # Let's see how many conflicts we find
    matches = re.findall(conflict_pattern, content)
    print(f"Found {len(matches)} conflicts.")
    
    # We replace each conflict with the second group (remote changes)
    resolved_content = re.sub(conflict_pattern, r"\2", content)
    
    with open(values_path, 'w', encoding='utf-8') as f:
        f.write(resolved_content)
    print("Conflicts resolved successfully!")

if __name__ == '__main__':
    resolve_conflicts()
