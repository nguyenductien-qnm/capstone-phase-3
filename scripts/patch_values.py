import re

values_path = r"C:\Users\THANH TRUNG\Desktop\Phase3\capstone-phase-3\platform\charts\application\values.yaml"

def patch_values():
    with open(values_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Define resource limits/requests mapping for each service.
    resource_limits_memory = {
        'accounting': '120Mi',
        'ad': '300Mi',
        'cart': '160Mi',
        'checkout': '20Mi',
        'currency': '20Mi',
        'email': '100Mi',
        'fraud-detection': '300Mi',
        'frontend': '250Mi',
        'frontend-proxy': '65Mi',
        'image-provider': '50Mi',
        'load-generator': '1500Mi',
        'payment': '140Mi',
        'product-catalog': '20Mi',
        'product-reviews': '512Mi',
        'quote': '40Mi',
        'recommendation': '500Mi',
        'shipping': '20Mi',
        'flagd': '75Mi',
        'llm': '512Mi'
    }

    def get_resource_block(comp):
        mem_limit = resource_limits_memory.get(comp, '100Mi')
        cpu_req = '10m'
        mem_req = '32Mi'
        cpu_limit = '100m'
        
        if comp in ['frontend', 'frontend-proxy']:
            cpu_req = '20m'
            mem_req = '64Mi'
            cpu_limit = '200m'
        elif comp == 'load-generator':
            cpu_req = '50m'
            mem_req = '128Mi'
            cpu_limit = '500m'
        elif comp == 'llm':
            cpu_req = '50m'
            mem_req = '128Mi'
            cpu_limit = '500m'
        elif comp == 'product-reviews':
            # product-reviews already has requests and limits in values.yaml
            return None
            
        return f"""    resources:
      requests:
        cpu: {cpu_req}
        memory: {mem_req}
      limits:
        cpu: {cpu_limit}
        memory: {mem_limit}
"""

    new_lines = []
    i = 0
    current_component = None

    while i < len(lines):
        line = lines[i]
        
        # 1. Detect component block start (e.g. `  accounting:`)
        comp_match = re.match(r'^  ([a-zA-Z0-9_-]+):\s*$', line)
        if comp_match:
            current_component = comp_match.group(1)
            new_lines.append(line)
            i += 1
            continue

        # If line starts with less than 4 spaces and is not empty or comment, we left the component
        if current_component and not line.startswith('    ') and line.strip() and not line.strip().startswith('#'):
            current_component = None

        if current_component:
            # We are inside a component
            # A. Look for resources block belonging to this component
            if line.startswith('    resources:'):
                res_block = get_resource_block(current_component)
                if res_block:
                    # Consume all lines belonging to this resources block (indented > 4 spaces)
                    i += 1
                    while i < len(lines) and (lines[i].startswith('      ') or not lines[i].strip()):
                        i += 1
                    # Output our new resources block for this component
                    new_lines.append(res_block)
                    continue

        new_lines.append(line)
        i += 1

    content = "".join(new_lines)

    # Now we apply exact string replacements for default securityContext, initContainers, local securityContexts
    
    # default securityContext
    content = content.replace("  securityContext: {}", """  # Default securityContext for all components
  securityContext:
    allowPrivilegeEscalation: false
    runAsNonRoot: true
    capabilities:
      drop:
        - ALL
  # Default podSecurityContext for all components
  podSecurityContext:
    runAsNonRoot: true
    seccompProfile:
      type: RuntimeDefault""")

    # initContainers
    init_configs = [
        # accounting / checkout / fraud-detection wait-for-kafka
        (
            """    initContainers:
      - name: wait-for-kafka
        image: busybox:latest
        command: ["sh", "-c", "until nc -z -v -w30 b-1.ecommercedevmsk.61s37h.c4.kafka.us-east-1.amazonaws.com 9096; do echo waiting for kafka; sleep 2; done;"]""",
            """    initContainers:
      - name: wait-for-kafka
        image: busybox:1.36.1
        command: ["sh", "-c", "until nc -z -v -w30 b-1.ecommercedevmsk.61s37h.c4.kafka.us-east-1.amazonaws.com 9096; do echo waiting for kafka; sleep 2; done;"]
        securityContext:
          runAsUser: 1000
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL"""
        ),
        # cart wait-for-valkey-cart
        (
            """    initContainers:
      - name: wait-for-valkey-cart
        image: busybox:latest
        command: ["sh", "-c", "until nc -z -v -w30 master.ecommerce-dev-valkey.7ylfic.use1.cache.amazonaws.com 6379; do echo waiting for valkey-cart; sleep 2; done;"]""",
            """    initContainers:
      - name: wait-for-valkey-cart
        image: busybox:1.36.1
        command: ["sh", "-c", "until nc -z -v -w30 master.ecommerce-dev-valkey.7ylfic.use1.cache.amazonaws.com 6379; do echo waiting for valkey-cart; sleep 2; done;"]
        securityContext:
          runAsUser: 1000
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL"""
        ),
        # flagd init-config (image: busybox can be busybox:latest or busybox:1.38.0 on develop)
        # Let's replace whatever init-config contains
        (
            """    initContainers:
      - name: init-config
        image: busybox
        command: ["sh", "-c", "cp /config-ro/demo.flagd.json /config-rw/demo.flagd.json && cat /config-rw/demo.flagd.json"]
        volumeMounts:
          - mountPath: /config-ro
            name: config-ro
          - mountPath: /config-rw
            name: config-rw""",
            """    initContainers:
      - name: init-config
        image: busybox:1.36.1
        command: ["sh", "-c", "cp /config-ro/demo.flagd.json /config-rw/demo.flagd.json && cat /config-rw/demo.flagd.json"]
        securityContext:
          runAsUser: 1000
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
        volumeMounts:
          - mountPath: /config-ro
            name: config-ro
          - mountPath: /config-rw
            name: config-rw"""
        )
    ]
    
    # We should also handle if flagd busybox tag was already modified to something else by develop pull
    # In line 1198 view_file output we saw:
    #     image: busybox:1.38.0   # Pinned: was untagged (defaults to :latest).
    # Let's add that to init_configs too!
    init_configs.append((
            """    initContainers:
      - name: init-config
        image: busybox:1.38.0   # Pinned: was untagged (defaults to :latest).
        command: ["sh", "-c", "cp /config-ro/demo.flagd.json /config-rw/demo.flagd.json && cat /config-rw/demo.flagd.json"]
        volumeMounts:
          - mountPath: /config-ro
            name: config-ro
          - mountPath: /config-rw
            name: config-rw""",
            """    initContainers:
      - name: init-config
        image: busybox:1.36.1
        command: ["sh", "-c", "cp /config-ro/demo.flagd.json /config-rw/demo.flagd.json && cat /config-rw/demo.flagd.json"]
        securityContext:
          runAsUser: 1000
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
        volumeMounts:
          - mountPath: /config-ro
            name: config-ro
          - mountPath: /config-rw
            name: config-rw"""
    ))
    
    for old, new in init_configs:
        content = content.replace(old, new)

    # local securityContexts
    local_security_contexts = [
        # frontend
        (
            """    securityContext:
      runAsUser: 1001  # nextjs
      runAsGroup: 1001
      runAsNonRoot: true""",
            """    securityContext:
      runAsUser: 1001  # nextjs
      runAsGroup: 1001
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL"""
        ),
        # frontend-proxy
        (
            """    securityContext:
      runAsUser: 101  # envoy
      runAsGroup: 101
      runAsNonRoot: true""",
            """    securityContext:
      runAsUser: 101  # envoy
      runAsGroup: 101
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL"""
        ),
        # payment
        (
            """    securityContext:
      runAsUser: 1000  # node
      runAsGroup: 1000
      runAsNonRoot: true""",
            """    securityContext:
      runAsUser: 1000  # node
      runAsGroup: 1000
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL"""
        ),
        # quote
        (
            """    securityContext:
      runAsUser: 33  # www-data
      runAsGroup: 33
      runAsNonRoot: true""",
            """    securityContext:
      runAsUser: 33  # www-data
      runAsGroup: 33
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL"""
        ),
        # kafka
        (
            """    securityContext:
      runAsUser: 1000  # appuser
      runAsGroup: 1000
      runAsNonRoot: true""",
            """    securityContext:
      runAsUser: 1000  # appuser
      runAsGroup: 1000
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL"""
        ),
        # valkey-cart
        (
            """    securityContext:
      runAsUser: 999  # valkey
      runAsGroup: 1000
      runAsNonRoot: true""",
            """    securityContext:
      runAsUser: 999  # valkey
      runAsGroup: 1000
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL"""
        )
    ]
    for old, new in local_security_contexts:
        content = content.replace(old, new)

    # ad service injection
    # Replace ad: ... with ad service resources and securityContext
    ad_old = """  ad:
    enabled: true
    useDefault:
      env: true
    service:
      port: 8080
    podAnnotations:
      resource.opentelemetry.io/service.namespace: techx-corp
    env:
      - name: AD_PORT
        value: "8080"
      - name: FLAGD_HOST
        value: flagd
      - name: FLAGD_PORT
        value: "8013"
      - name: OTEL_EXPORTER_OTLP_ENDPOINT
        value: http://$(OTEL_COLLECTOR_NAME):4318
      - name: OTEL_LOGS_EXPORTER
        value: otlp
    resources:
      requests:
        cpu: 10m
        memory: 32Mi
      limits:
        cpu: 100m
        memory: 300Mi"""
        
    ad_new = ad_old + """
    securityContext:
      runAsUser: 1000
      runAsNonRoot: true
      allowPrivilegeEscalation: false
      capabilities:
        drop:
          - ALL
      readOnlyRootFilesystem: true"""
    
    content = content.replace(ad_old, ad_new)

    # llm service injection
    llm_old = """  llm:
    enabled: true
    useDefault:
      env: true
    service:
      port: 8000
    podAnnotations:
      resource.opentelemetry.io/service.namespace: techx-corp
    env:
      - name: FLAGD_HOST
        value: flagd
      - name: FLAGD_PORT
        value: "8013\""""
        
    llm_new = llm_old + """
    resources:
      requests:
        cpu: 50m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 512Mi"""
        
    content = content.replace(llm_old, llm_new)

    with open(values_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Values patched successfully!")

if __name__ == '__main__':
    patch_values()
