// Test-only adapters. Not included in the published browser application.
import assert from "node:assert/strict";
import {DatabaseSync} from "node:sqlite";
import {readFileSync} from "node:fs";
import {createHash,randomBytes} from "node:crypto";
import {handle} from "../worker/index.mjs";
export const raw=()=>randomBytes(32).toString("base64url");
export const digest=s=>createHash("sha256").update(s).digest("base64url");
export const api="https://sync.example", origin="https://club.example";
export function harness(){
  const sql=new DatabaseSync(":memory:");
  sql.exec(readFileSync(new URL("../schema.sql",import.meta.url),"utf8"));
  const env={APP_URL:origin+"/trainer/",WCA_CLIENT_ID:"demo-client",WCA_CLIENT_SECRET:"test-secret",DB:{
    prepare(s){return {bind(...args){
      const stmt=sql.prepare(s),a=args.map(x=>x instanceof ArrayBuffer?new Uint8Array(x):x);
      return {first:()=>stmt.get(...a)||null,run:()=>({meta:stmt.run(...a)})};
    }};},
    batch(stmt){sql.exec("BEGIN");try{const r=stmt.map(s=>s.run());sql.exec("COMMIT");return r;}catch(e){sql.exec("ROLLBACK");throw e;}}
  }};
  let account=10, expectedProof, rejectProfile=false;
  const provider=async (url,opts)=>{
    if(url.endsWith("/oauth/token")){
      assert.equal(opts.body.get("redirect_uri"),api+"/auth/callback");
      assert.equal(opts.body.get("client_secret"),env.WCA_CLIENT_SECRET);
      assert.equal(digest(opts.body.get("code_verifier")),expectedProof);
      assert.equal(opts.body.get("code"),"mock-code");
      return Response.json({access_token:"ephemeral-provider-token"});
    }
    assert.equal(url,"https://www.worldcubeassociation.org/api/v0/me");
    assert.equal(opts.headers.Authorization,"Bearer ephemeral-provider-token");
    return rejectProfile ? new Response(null,{status:500}):Response.json({me:{id:account,name:"Test cuber",wca_id:null,email:"unused@example.invalid"}});
  };
  const send=(path,options={})=>handle(new Request(api+path,options),env,provider);
  const request=(method,path,token,body)=>send(path,{method,headers:{Origin:origin,"Content-Type":"application/json",...(token?{Authorization:"Bearer "+token}:{})},
    ...(body===undefined?{}:{body:JSON.stringify(body)})});
  async function start(){
    const verifier=raw(),browser=raw();
    const res=await send("/auth/start?"+new URLSearchParams({state:browser,challenge:digest(verifier)}));
    assert.equal(res.status,303);
    const loc=new URL(res.headers.get("Location")),cookie=res.headers.get("Set-Cookie");
    assert.equal(loc.origin,"https://www.worldcubeassociation.org");
    assert.match(cookie,/HttpOnly; SameSite=Lax/);
    assert.equal(loc.searchParams.get("scope"),"public");
    expectedProof=loc.searchParams.get("code_challenge");
    return {verifier,browser,state:loc.searchParams.get("state"),cookie:cookie.split(";")[0]};
  }
  async function complete(flow, suffix="&code=mock-code"){
    const res=await send("/auth/callback?state="+flow.state+suffix,{headers:{Cookie:flow.cookie}});
    const u=new URL(res.headers.get("Location"));
    assert.equal(u.origin+u.pathname,origin+"/trainer/account.html");
    return Object.fromEntries(new URLSearchParams(u.hash.slice(1)));
  }
  const exchange=(ticket,verifier)=>request("POST","/auth/exchange",null,{ticket,verifier});
  async function login(id){
    account=id;const f=await start(),r=await complete(f);assert.equal(r.state,f.browser);
    const res=await exchange(r.ticket,f.verifier);
    assert.equal(res.status,200);return res.json();
  }
  return {sql,env,send,request,start,complete,login,exchange,fail:()=>{rejectProfile=true;}};
}

export function memoryIDB(){
  const data=new Map();
  return {open(){const r={};queueMicrotask(()=>{
    r.result={transaction(){
      const tx={};let pending=0,finished=false;
      const finish=()=>{if(!pending&&!finished){finished=true;tx.oncomplete();}};
      const store={get(key){const q={};pending++;queueMicrotask(()=>{
        q.result=structuredClone(data.get(key));q.onsuccess?.();pending--;queueMicrotask(finish);
      });return q;},put(v,k){data.set(k,structuredClone(v));},delete(k){data.delete(k);}};
      tx.abort=()=>{if(!finished){finished=true;queueMicrotask(()=>tx.onabort());}};
      tx.objectStore=()=>store;return tx;
    },createObjectStore(){}};
    r.onupgradeneeded?.();r.onsuccess();
  });return r;}};
}
