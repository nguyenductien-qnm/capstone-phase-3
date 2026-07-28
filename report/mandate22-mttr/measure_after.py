import json,subprocess,time
from datetime import datetime
NS="techx-tf1";SEL="opentelemetry.io/name=mttr-canary"
def kj(*a):
    o=subprocess.run(["kubectl","-n",NS,*a,"-o","json"],capture_output=True,text=True,timeout=30)
    return json.loads(o.stdout) if o.stdout.strip() else None
def ts(s):
    return datetime.fromisoformat(s.replace("Z","+00:00")).timestamp() if s else None
def snap():
    d=kj("get","pods","-l",SEL)
    if not d or not d.get("items"): return None
    p=d["items"][0];cs=(p["status"].get("containerStatuses") or [{}])[0]
    t=(cs.get("lastState",{}) or {}).get("terminated",{}) or {}
    return {"pod":p["metadata"]["name"],"ready":cs.get("ready",False),
            "created":ts(p["metadata"]["creationTimestamp"]),
            "oom":ts(t.get("finishedAt")) if t.get("reason")=="OOMKilled" else None}
f=open("/tmp/r2.txt","w",buffering=1)
p0=snap();f.write(f"{datetime.now():%H:%M:%S} theo doi pod {p0['pod']}\n")
last_oom=p0["oom"];t0=time.time()
while time.time()-t0<600:
    time.sleep(3);s=snap()
    if not s: continue
    if s["oom"] and s["oom"]!=last_oom:
        last_oom=s["oom"];f.write(f"{datetime.now():%H:%M:%S} OOM luc {datetime.fromtimestamp(s['oom']):%H:%M:%S}\n")
    if s["pod"]!=p0["pod"]:
        f.write(f"{datetime.now():%H:%M:%S} POD MOI {s['pod']}\n")
        while time.time()-t0<600:
            r=snap()
            if r and r["ready"] and r["pod"]==s["pod"]:
                n=time.time()
                f.write("\n"+"="*50+"\n")
                f.write(f"  OOM cuoi      : {datetime.fromtimestamp(last_oom):%H:%M:%S}\n")
                f.write(f"  pod moi tao   : {datetime.fromtimestamp(s['created']):%H:%M:%S}\n")
                f.write(f"  pod moi Ready : {datetime.now():%H:%M:%S}\n")
                f.write(f"  OOM->xoa      : {s['created']-last_oom:.1f}s\n")
                f.write(f"  MTTR (after)  : {n-last_oom:.1f}s\n"+"="*50+"\n")
                json.dump({"label":"after","mttr":n-last_oom,"oom_to_delete":s["created"]-last_oom,
                           "old_pod":p0["pod"],"new_pod":s["pod"]},
                          open("report/mandate15/mttr-after.json","w"),indent=2)
                f.close();raise SystemExit
            time.sleep(3)
    p0=s
f.write("het gio\n");f.close()
