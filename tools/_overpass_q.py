import requests, json, sys, time
M=["https://maps.mail.ru/osm/tools/overpass/api/interpreter","https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter","https://overpass.private.coffee/api/interpreter"]
def q(txt):
    for m in M:
        try:
            r=requests.post(m,data={"data":txt},timeout=120,headers={"User-Agent":"AnalystEye/1.0 (daily geo puzzle; https://x.com/A_is_A)"})
            if r.status_code==200: return r.json()["elements"]
            print(m,r.status_code,file=sys.stderr)
        except Exception as e: print(m,e,file=sys.stderr)
    return None
if __name__=="__main__":
    out=q(sys.argv[1]); print(len(out) if out is not None else None)
    if out: 
        for e in out[:int(sys.argv[2]) if len(sys.argv)>2 else 5]: print(e["type"],e["id"],e.get("tags"),e.get("lat"),e.get("center"))
