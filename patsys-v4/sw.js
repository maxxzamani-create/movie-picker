const C='pt-v4';
self.addEventListener('install',e=>{self.skipWaiting();});
self.addEventListener('activate',e=>{e.waitUntil((async()=>{for(const k of await caches.keys()) if(k!==C) await caches.delete(k); await self.clients.claim();})());});
// Network first, so a new version always shows; the cache is only the fallback when the venue wifi is down.
self.addEventListener('fetch',e=>{
  const req=e.request; if(req.method!=='GET') return;
  const url=req.url.split('#')[0]; const range=req.headers.get('range');
  e.respondWith((async()=>{
    const c=await caches.open(C);
    try{ const r=await fetch(req); if(r.ok&&r.status===200&&!range) c.put(url,r.clone()); return r; }
    catch(err){
      const hit=await c.match(url,{ignoreSearch:true}); if(!hit) throw err;
      if(range){ const buf=await hit.clone().arrayBuffer(); const m=/bytes=(\d+)-(\d*)/.exec(range); const s=+m[1], en=m[2]?+m[2]:buf.byteLength-1;
        return new Response(buf.slice(s,en+1),{status:206,headers:{'Content-Type':hit.headers.get('Content-Type')||'video/mp4','Content-Range':`bytes ${s}-${en}/${buf.byteLength}`,'Content-Length':String(en-s+1),'Accept-Ranges':'bytes'}}); }
      return hit; }
  })());
});
