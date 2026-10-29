import json, time, sys
from _overpass_q import q
# Gulf bbox [29.85,-90.35,30.75,-87.45]; 4 lon tiles x 2 lat tiles
S,W,N,E=29.85,-90.35,30.75,-87.45
lons=[W+(E-W)*i/4 for i in range(5)]; lats=[S,(S+N)/2,N]
sels={
 "lot": 'way["amenity"="parking"]["parking"!~"multi-storey|underground|street_side|lane|rooftop"]["access"!~"private|no"]({b});',
 "garage": '(way["amenity"="parking"]["parking"="multi-storey"]({b});way["building"="parking"]({b}););',
 "quarry": '(way["landuse"="quarry"]({b});relation["landuse"="quarry"]({b}););',
 "yard": '(way["landuse"="railway"]({b});way["railway"="yard"]({b}););',
 "silo": '(way["man_made"="silo"]({b});node["man_made"="silo"]({b});way["building"="silo"]({b}););',
}
out={}
for name,sel in sels.items():
    out[name]=[]
    for i in range(4):
        for j in range(2):
            b=f"{lats[j]:.4f},{lons[i]:.4f},{lats[j+1]:.4f},{lons[i+1]:.4f}"
            txt=f'[out:json][timeout:90];{sel.format(b=b)}out tags center geom;'
            r=None
            for t in range(3):
                r=q(txt)
                if r is not None: break
                time.sleep(8)
            print(name,i,j,None if r is None else len(r),flush=True)
            if r: out[name]+=r
            json.dump(out,open((sys.argv[1] if len(sys.argv) > 1 else "raw/bulk.json"),"w"))
