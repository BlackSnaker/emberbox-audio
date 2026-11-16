import { defineConfig } from "vite";
import { createHash } from "node:crypto";
export default defineConfig({
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [{ name: "three", test: /node_modules\/three/ }],
        },
      },
    },
  },
  plugins: [
    {
      name: "ember-offline-shell",
      generateBundle(_options, bundle) {
        const assets = [
          "/",
          "/demo-cover.png",
          "/manifest.webmanifest",
          "/icon-192.png",
          "/icon-512.png",
          ...Object.keys(bundle)
            .filter((v) => v.endsWith(".js") || v.endsWith(".css"))
            .map((v) => "/" + v),
        ];
        const version = createHash("sha256")
          .update(JSON.stringify(assets))
          .digest("hex")
          .slice(0, 12);
        this.emitFile({
          type: "asset",
          fileName: "sw.js",
          source: `const CACHE='ember-quest-${version}',ASSETS=${JSON.stringify(assets)};
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('activate',e=>e.waitUntil(Promise.all([self.clients.claim(),caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('ember-quest-')&&k!==CACHE).map(k=>caches.delete(k))))])));
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==location.origin||u.pathname.startsWith('/api/'))return;
e.respondWith((async()=>{const c=await caches.open(CACHE);try{const r=await fetch(e.request);if(r.ok&&ASSETS.includes(u.pathname))await c.put(u.pathname,r.clone());return r;}catch{const r=await c.match(u.pathname);return r||(e.request.mode==='navigate'?await c.match('/'):null)||Response.error();}})());});`,
        });
      },
    },
  ],
});
