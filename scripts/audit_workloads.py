import yaml
import sys
import os

manifest_path = r"C:\Users\THANH TRUNG\.gemini\antigravity-ide\scratch\rendered_manifests.yaml"

def audit_workloads():
    if not os.path.exists(manifest_path):
        print(f"File not found: {manifest_path}")
        return

    with open(manifest_path, 'r', encoding='utf-16') as f:
        content = f.read()

    # Split documents by ---
    docs = content.split('\n---\n')
    
    results = []

    for doc_str in docs:
        if not doc_str.strip():
            continue
        try:
            doc = yaml.safe_load(doc_str)
        except Exception as e:
            # Skip invalid yaml blocks
            continue

        if not doc or not isinstance(doc, dict):
            continue

        kind = doc.get('kind')
        if kind not in ['Deployment', 'StatefulSet', 'DaemonSet', 'Job', 'Pod']:
            continue

        name = doc.get('metadata', {}).get('name', 'unknown')
        namespace = doc.get('metadata', {}).get('namespace', 'default')

        # Get pod spec
        spec = {}
        if kind == 'Pod':
            spec = doc.get('spec', {})
        else:
            spec = doc.get('spec', {}).get('template', {}).get('spec', {})

        if not spec:
            continue

        pod_sec_ctx = spec.get('securityContext', {}) or {}
        pod_run_as_non_root = pod_sec_ctx.get('runAsNonRoot')
        pod_run_as_user = pod_sec_ctx.get('runAsUser')

        # Audit helper
        def audit_containers(containers, c_type):
            for c in containers:
                c_name = c.get('name', 'unknown')
                image = c.get('image', '')
                sec_ctx = c.get('securityContext', {}) or {}
                
                run_as_non_root = sec_ctx.get('runAsNonRoot')
                if run_as_non_root is None:
                    run_as_non_root = pod_run_as_non_root

                run_as_user = sec_ctx.get('runAsUser')
                if run_as_user is None:
                    run_as_user = pod_run_as_user

                allow_privilege_escalation = sec_ctx.get('allowPrivilegeEscalation')
                capabilities = sec_ctx.get('capabilities', {}) or {}
                cap_drop = capabilities.get('drop', [])
                read_only_fs = sec_ctx.get('readOnlyRootFilesystem')

                status = "Pass"
                details = []

                if run_as_non_root is not True and (run_as_user is None or run_as_user == 0):
                    status = "Fail"
                    details.append("chạy quyền root / thiếu runAsNonRoot")
                
                if allow_privilege_escalation is not False:
                    status = "Fail"
                    details.append("thiếu allowPrivilegeEscalation=false")

                if not cap_drop or "ALL" not in [x.upper() for x in cap_drop]:
                    status = "Fail"
                    details.append("thiếu drop capabilities (ALL)")

                if read_only_fs is not True:
                    if status != "Fail":
                        status = "Cần xác minh"
                    details.append("thiếu readOnlyRootFilesystem")

                if not details:
                    details_str = "Đầy đủ bảo mật"
                else:
                    details_str = ", ".join(details)

                results.append({
                    'workload_kind': kind,
                    'workload_name': name,
                    'namespace': namespace,
                    'container_type': c_type,
                    'container_name': c_name,
                    'image': image,
                    'run_as_non_root': str(run_as_non_root),
                    'run_as_user': str(run_as_user),
                    'allow_privilege_escalation': str(allow_privilege_escalation),
                    'cap_drop': str(cap_drop),
                    'read_only_fs': str(read_only_fs),
                    'status': status,
                    'details': details_str
                })

        audit_containers(spec.get('containers', []), 'container')
        audit_containers(spec.get('initContainers', []) or [], 'initContainer')

    # Output results as Markdown Table to file
    out_path = r"C:\Users\THANH TRUNG\.gemini\antigravity-ide\scratch\audit_results.md"
    with open(out_path, 'w', encoding='utf-8') as out_f:
        out_f.write("| Workload (Kind/Name) | Container (Type) | Image | nonRoot | User | allowPrivEsc | Drop Caps | readOnlyFS | Status | Chi tiết / Điểm thiếu |\n")
        out_f.write("| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |\n")
        for r in sorted(results, key=lambda x: (x['workload_kind'], x['workload_name'])):
            out_f.write(f"| `{r['workload_kind']}/{r['workload_name']}` | `{r['container_name']}` ({r['container_type']}) | `{r['image']}` | {r['run_as_non_root']} | {r['run_as_user']} | {r['allow_privilege_escalation']} | {r['cap_drop']} | {r['read_only_fs']} | **{r['status']}** | {r['details']} |\n")
    print(f"Audit completed successfully! Results written to: {out_path}")

if __name__ == '__main__':
    audit_workloads()
