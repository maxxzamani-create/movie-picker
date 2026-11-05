const C='th-fall-v2';
self.addEventListener('install',e=>{self.skipWaiting();});
self.addEventListener('activate',e=>{e.waitUntil(self.clients.claim());});
self.addEventListener('fetch',e=>{
  const req=e.request; if(req.method!=='GET') return;
  e.respondWith((async()=>{
    const c=await caches.open(C);
    const range=req.headers.get('range');
    let hit=await c.match(req.url.split('#')[0],{ignoreSearch:true});
    if(!hit){ try{ const r=await fetch(req.url.split('#')[0]); if(r.ok&&r.status===200) c.put(req.url.split('#')[0],r.clone()); if(!range) return r; hit=r; }catch(err){ return fetch(req); } }
    if(range && hit){ const buf=await hit.clone().arrayBuffer(); const m=/bytes=(\d+)-(\d*)/.exec(range); const s=+m[1], en=m[2]?+m[2]:buf.byteLength-1;
      return new Response(buf.slice(s,en+1),{status:206,headers:{'Content-Type':hit.headers.get('Content-Type')||'video/mp4','Content-Range':`bytes ${s}-${en}/${buf.byteLength}`,'Content-Length':String(en-s+1),'Accept-Ranges':'bytes'}}); }
    return hit;
  })());
});