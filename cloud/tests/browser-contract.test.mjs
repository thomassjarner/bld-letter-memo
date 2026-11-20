// Same modules deployed to Pages, with tab storage and IndexedDB transactions
// modelled in memory. These are JavaScript contract tests, not browser rendering tests.
import test from "node:test";
import {memoryIDB} from "./fixtures.mjs";
import assert from "node:assert/strict";
import {mkdtemp,copyFile,writeFile,rm} from "node:fs/promises";
import {join} from "node:path";
import {tmpdir} from "node:os";
import {pathToFileURL} from "node:url";
import {randomBytes,createHash} from "node:crypto";
const folder=await mkdtemp(join(tmpdir(),"bld-cloud-test-"));
for(const file of ["cloud-store.mjs","account.mjs"]) await copyFile(new URL("../../web_cloud/"+file,import.meta.url),join(folder,file));
await writeFile(join(folder,"cloud-endpoint.mjs"),'export const API="https://sync.example";');
const {handleLogin}=await import(pathToFileURL(join(folder,"account.mjs")));
const {connect,call}=await import(pathToFileURL(join(folder,"cloud-store.mjs")));
test.after(()=>rm(folder,{recursive:true,force:true}));
function tab(){
  const fields=new Map();
  return {location:{hash:"",pathname:"/app/account.html",replace(url){this.next=String(url);}},
    history:{replaceState(a,b,url){this.clean=url;}},
    sessionStorage:{getItem:k=>fields.get(k),setItem:(k,v)=>fields.set(k,v),removeItem:k=>fields.delete(k)}};
}
test("sign-in roundtrip uses the same tab, removes the handoff and returns to Settings",async()=>{
  const t=tab();await handleLogin(t);
  const url=new URL(t.location.next);
  assert.equal(url.origin+url.pathname,"https://sync.example/auth/start");
  const state=url.searchParams.get("state"),challenge=url.searchParams.get("challenge");
  t.location.hash="#"+new URLSearchParams({ticket:"one-time",state});
  const wrongTab=tab();wrongTab.location.hash=t.location.hash;
  await assert.rejects(handleLogin(wrongTab,()=>assert.fail()),/same browser tab/);
  await handleLogin(t,async(ticket,key)=>{
    assert.equal(t.history.clean,t.location.pathname);assert.equal(ticket,"one-time");
    assert.equal(createHash("sha256").update(key).digest("base64url"),challenge);
  });
  assert.ok(t.location.next.endsWith("/#/account"));
  await assert.rejects(handleLogin(t,()=>assert.fail()),/same browser tab/);
});
test("cancelling leaves the old workspace alone",async()=>{
  const t=tab();await handleLogin(t);t.location.hash="#error=cancelled";
  await assert.rejects(handleLogin(t,()=>assert.fail()),/cancelled/);
});

test("trainer session stays outside exports and one tab cannot act as a newly signed-in account",async()=>{
  const before=globalThis.fetch;const original=globalThis.indexedDB;
  globalThis.indexedDB=memoryIDB();let id=42;const sessions=new Map();
  const raw=()=>randomBytes(32).toString("base64url");
  globalThis.fetch=async(url,opts)=>{
    if(url.endsWith("/auth/exchange")){
      const token=raw();sessions.set(token,id);
      return Response.json({user:{id,name:"Cuber",wca_id:""},token,expires:Date.now()/1000+3000});
    }
    assert.equal(opts.credentials,"omit");const account=sessions.get(opts.headers.Authorization.slice(7));
    assert.equal(account,id);
    return Response.json({revision:1,workspace:{version:18}});
  };
  const invoke=async(op,args={})=>JSON.parse(await call(op,JSON.stringify(args)));
  try {
    await connect(raw(),raw());
    const first=(await invoke("info")).value;assert.equal(first.enabled,false);assert.ok(!("token" in first));
    assert.equal((await invoke("read",{tag:first.tag})).value.revision,1);
    await invoke("commit",{tag:first.tag,revision:2,workspace:{global_words:{IR:"iris"}}});
    await invoke("commit",{tag:first.tag,revision:1,workspace:{}});
    assert.equal((await invoke("base",{tag:first.tag})).value.workspace.global_words.IR,"iris");
    id=43;await connect(raw(),raw());
    assert.equal((await invoke("read",{tag:first.tag})).status,401);
    await invoke("forget",{tag:first.tag});const next=(await invoke("info")).value;
    assert.equal(next.user.id,43);assert.equal(next.enabled,false);assert.equal((await invoke("base",{tag:next.tag})).value,null);
    await invoke("forget",{tag:next.tag});assert.equal((await invoke("info")).value,null);
  } finally {globalThis.fetch=before;globalThis.indexedDB=original;}
});
