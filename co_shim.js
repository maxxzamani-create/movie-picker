/*
 * Static-hosting shim for the Commercial Override demo.
 *
 * The full product runs a Flask backend (see the movie-picker repo). This
 * shim emulates the /co/api/* endpoints entirely in the browser so the demo
 * can be hosted as plain static files: settings and impression stats persist
 * in localStorage; uploaded spots live for the session via object URLs.
 */
(function () {
  const LS_KEY = "co_demo_v1";

  const BUILTIN_ADS = [
    { id: "burger", name: "Zenie Burger — ½ Price",
      url: "static/co/ad_burger.mp4", url_webm: "static/co/ad_burger.webm",
      enabled: true, builtin: true },
    { id: "wings", name: "50¢ Wing Night",
      url: "static/co/ad_wings.mp4", url_webm: "static/co/ad_wings.webm",
      enabled: true, builtin: true },
    { id: "happyhour", name: "Happy Hour 4–7",
      url: "static/co/ad_happyhour.mp4", url_webm: "static/co/ad_happyhour.webm",
      enabled: true, builtin: true },
  ];

  const sessionAds = [];   // uploaded this session (object URLs don't persist)

  function store() {
    try { return JSON.parse(localStorage.getItem(LS_KEY)) || {}; }
    catch (e) { return {}; }
  }
  function save(s) { localStorage.setItem(LS_KEY, JSON.stringify(s)); }

  function currentAds() {
    const disabled = new Set(store().disabled_ads || []);
    const builtins = BUILTIN_ADS.map(a => ({ ...a, enabled: !disabled.has(a.id) }));
    return builtins.concat(sessionAds);
  }

  function json(obj, status) {
    return new Response(JSON.stringify(obj), {
      status: status || 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const realFetch = window.fetch.bind(window);

  window.fetch = async function (url, opts) {
    const u = typeof url === "string" ? url : url.url;
    if (!u.startsWith("/co/api")) return realFetch(url, opts);
    const method = ((opts && opts.method) || "GET").toUpperCase();
    const s = store();

    // GET /co/api/state
    if (u === "/co/api/state" && method === "GET") {
      let analysis;
      try {
        analysis = await (await realFetch("static/co/game_feed.analysis.json")).json();
      } catch (e) {
        analysis = { commercial_windows: [], duration: 75 };
      }
      return json({
        business_name: s.business_name || "Maxx's Bar & Grill",
        override_enabled: s.override_enabled !== false,
        ads: currentAds(),
        feed_url: "static/co/game_feed.mp4",
        feed_url_webm: "static/co/game_feed.webm",
        analysis: analysis,
      });
    }

    // POST /co/api/settings
    if (u === "/co/api/settings" && method === "POST") {
      const body = JSON.parse(opts.body || "{}");
      if ("business_name" in body && String(body.business_name).trim())
        s.business_name = String(body.business_name).trim().slice(0, 80);
      if ("override_enabled" in body)
        s.override_enabled = !!body.override_enabled;
      save(s);
      return json({ ok: true });
    }

    // POST /co/api/ads  (upload — session only on static hosting)
    if (u === "/co/api/ads" && method === "POST") {
      const fd = opts.body;
      const file = fd && fd.get && fd.get("file");
      if (!file || !file.name) return json({ error: "No file provided" }, 400);
      const objUrl = URL.createObjectURL(file);
      const ad = {
        id: "s" + Math.random().toString(36).slice(2, 10),
        name: (fd.get("name") || "").trim() || file.name,
        url: objUrl, url_webm: null, enabled: true, builtin: false,
      };
      sessionAds.push(ad);
      return json({ ok: true, ad: ad });
    }

    // POST /co/api/ads/<id>/toggle
    let m = u.match(/^\/co\/api\/ads\/([^/]+)\/toggle$/);
    if (m && method === "POST") {
      const id = m[1];
      const sess = sessionAds.find(a => a.id === id);
      if (sess) { sess.enabled = !sess.enabled; return json({ ok: true, enabled: sess.enabled }); }
      const disabled = new Set(s.disabled_ads || []);
      if (disabled.has(id)) disabled.delete(id); else disabled.add(id);
      s.disabled_ads = [...disabled];
      save(s);
      return json({ ok: true, enabled: !s.disabled_ads.includes(id) });
    }

    // DELETE /co/api/ads/<id>
    m = u.match(/^\/co\/api\/ads\/([^/]+)$/);
    if (m && method === "DELETE") {
      const i = sessionAds.findIndex(a => a.id === m[1]);
      if (i === -1) return json({ error: "Built-in demo ads can only be disabled" }, 400);
      URL.revokeObjectURL(sessionAds[i].url);
      sessionAds.splice(i, 1);
      return json({ ok: true });
    }

    // POST /co/api/impressions
    if (u === "/co/api/impressions" && method === "POST") {
      const body = JSON.parse(opts.body || "{}");
      const ad = currentAds().find(a => a.id === body.ad_id);
      if (!ad) return json({ error: "Unknown ad" }, 404);
      const log = s.impressions || [];
      log.unshift({
        ad_id: ad.id, ad_name: ad.name,
        at: new Date().toISOString().slice(0, 19),
        seconds: Math.round((body.seconds || 0) * 10) / 10,
      });
      s.impressions = log.slice(0, 500);
      save(s);
      return json({ ok: true });
    }

    // GET /co/api/impressions
    if (u === "/co/api/impressions" && method === "GET") {
      const log = s.impressions || [];
      const perAd = {};
      for (const imp of log) {
        const p = perAd[imp.ad_id] ||
          (perAd[imp.ad_id] = { ad_name: imp.ad_name, plays: 0, seconds: 0, last: imp.at });
        p.plays += 1;
        p.seconds = Math.round((p.seconds + imp.seconds) * 10) / 10;
      }
      return json({
        total_plays: log.length,
        total_seconds: Math.round(log.reduce((a, i) => a + i.seconds, 0) * 10) / 10,
        per_ad: perAd,
        recent: log.slice(0, 25),
      });
    }

    // POST /co/api/impressions/clear
    if (u === "/co/api/impressions/clear" && method === "POST") {
      s.impressions = [];
      save(s);
      return json({ ok: true });
    }

    return json({ error: "Unknown endpoint: " + u }, 404);
  };
})();
