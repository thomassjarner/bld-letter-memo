// Real SQLite, WebCrypto, Request/Response and gzip; only the WCA is simulated.
import test from "node:test";
import assert from "node:assert/strict";
import {raw,digest,api,origin,harness} from "./fixtures.mjs";
const ws={version:18,global_words:{IR:"iris"},practice_sessions:{"Session 1":[]},schemes:{}};
test("WCA → app callback → private session, including an account without a competitor ID",async()=>{
  const h=harness(),a=await h.login(42);
  assert.deepEqual(a.user,{id:42,name:"Test cuber",wca_id:""});assert.match(a.token,/^[\w-]{43}$/);
  assert.ok(!JSON.stringify(a).includes("provider-token"));
  const row=h.sql.prepare("SELECT * FROM sessions").get();
  assert.equal(row.token,digest(a.token));assert.equal(row.account,42);assert.ok(row.expires>Date.now()/1000);
  assert.equal(h.sql.prepare("SELECT COUNT(*) AS n FROM workspaces").get().n,0);
});
test("the browser return, one-time proof and expiry are required",async()=>{
  const h=harness(),f=await h.start();
  assert.equal((await h.complete({...f,cookie:""})).error,"expired");
  const valid=await h.complete(f);
  assert.equal((await h.complete(f)).error,"expired");
  assert.equal((await h.exchange(valid.ticket,raw())).status,401);
  assert.equal((await h.exchange(valid.ticket,f.verifier)).status,200);
  assert.equal((await h.exchange(valid.ticket,f.verifier)).status,401);
  const g=await h.start();h.sql.exec("UPDATE oauth_flows SET expires=0");
  assert.equal((await h.complete(g)).error,"expired");
});
test("cancel and a provider error leave no session or data",async()=>{
  const h=harness();
  assert.equal((await h.complete(await h.start(),"&error=access_denied")).error,"cancelled");
  h.fail();assert.equal((await h.complete(await h.start())).error,"unavailable");
  assert.equal(h.sql.prepare("SELECT COUNT(*) AS n FROM tickets").get().n,0);
});
test("private workspace roundtrip, cross-device revisions, independent accounts",async()=>{
  const h=harness(),a=await h.login(42),b=await h.login(42),other=await h.login(43);
  assert.deepEqual(await (await h.request("GET","/workspace",a.token)).json(),{revision:0,workspace:null});
  assert.equal((await h.request("PUT","/workspace",a.token,{revision:0,workspace:ws})).status,200);
  assert.equal((await h.request("PUT","/workspace",b.token,{revision:0,workspace:ws})).status,409);
  assert.deepEqual(await (await h.request("GET","/workspace?since=1",b.token)).json(),{revision:1,unchanged:true});
  assert.deepEqual(await (await h.request("GET","/workspace",b.token)).json(),{revision:1,workspace:ws});
  assert.deepEqual(await (await h.request("GET","/workspace?account=42",other.token)).json(),{revision:0,workspace:null});
  assert.equal((await h.request("PUT","/workspace",b.token,{revision:1,workspace:{...ws,global_words:{IR:"ice rink"}}})).status,200);
  assert.equal((await h.request("PUT","/workspace",a.token,{revision:1,workspace:ws})).status,409);
  assert.equal((await h.request("DELETE","/session",a.token)).status,200);
  assert.equal((await h.request("GET","/workspace",a.token)).status,401);
  assert.equal((await h.request("GET","/workspace",b.token)).status,200);
});
test("deletion revokes all devices of only that account, including stale pending writes",async()=>{
  const h=harness(),a=await h.login(12),b=await h.login(12),c=await h.login(11);
  for(const rec of [a,c]) assert.equal((await h.request("PUT","/workspace",rec.token,{revision:0,workspace:ws})).status,200);
  assert.equal((await h.request("DELETE","/account",b.token)).status,200);
  assert.equal((await h.request("PUT","/workspace",a.token,{revision:0,workspace:ws})).status,401);
  assert.equal((await h.request("GET","/workspace",c.token)).status,200);
  const again=await h.login(12);
  assert.deepEqual(await (await h.request("GET","/workspace",again.token)).json(),{revision:0,workspace:null});
});
test("configured origin, session, schema and bounded JSON; failed updates keep the prior revision",async()=>{
  const h=harness(),a=await h.login(12);
  const pre=await h.send("/workspace",{method:"OPTIONS",headers:{Origin:origin}});
  assert.equal(pre.headers.get("Access-Control-Allow-Origin"),origin);
  const denied=await h.send("/workspace",{headers:{Origin:"https://different.example"}});
  assert.equal(denied.status,403);assert.equal(denied.headers.get("Access-Control-Allow-Origin"),null);
  assert.equal((await h.request("GET","/workspace",null)).status,401);
  assert.equal((await h.request("PUT","/workspace",a.token,{revision:0,workspace:{...ws,version:19}})).status,422);
  const large=await h.send("/workspace",{method:"PUT",headers:{Origin:origin,"Content-Type":"application/json",Authorization:"Bearer "+a.token,"Content-Length":"9000000"},body:"{}"});
  assert.equal(large.status,413);
  h.sql.exec("UPDATE sessions SET expires=0");
  assert.equal((await h.request("GET","/workspace",a.token)).status,401);
});
test("sign-in throttling creates no WCA flow when a location has exhausted its allowance",async()=>{
  const h=harness();h.env.LOGIN_LIMIT={limit:async()=>({success:false})};
  const res=await h.send("/auth/start?"+new URLSearchParams({state:raw(),challenge:digest(raw())}));
  assert.equal(res.status,429);assert.equal(h.sql.prepare("SELECT COUNT(*) AS n FROM oauth_flows").get().n,0);
});
