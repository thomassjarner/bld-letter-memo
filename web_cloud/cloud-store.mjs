// Window and Pyodide module worker share this app-scoped IndexedDB. The WCA
// credential never reaches either; only an expiring, revocable trainer session does.
import {API} from "./cloud-endpoint.mjs";
const base=new URL(".",import.meta.url);
const dbName="bld-letter-memo.cloud:"+base.pathname+":"+API;
let openPromise;
function database(){
  if(!openPromise) openPromise=new Promise((resolve,reject)=>{
    const r=indexedDB.open(dbName,1);
    r.onupgradeneeded=()=>r.result.createObjectStore("device");
    r.onsuccess=()=>resolve(r.result);
    r.onerror=()=>{openPromise=null;reject(Error("Browser storage is unavailable."));};
  });
  return openPromise;
}
async function transaction(mode,fn){
  const db=await database();
  return new Promise((resolve,reject)=>{
    const tx=db.transaction("device",mode), store=tx.objectStore("device");let result, thrown;
    const req=store.get("account");
    req.onsuccess=()=>{try{result=fn(store,req.result);}catch(e){thrown=e;tx.abort();}};
    tx.oncomplete=()=>resolve(result);tx.onerror=tx.onabort=()=>reject(thrown||Error("Could not save the sync state on this device."));
  });
}
export const random=()=>encode(crypto.getRandomValues(new Uint8Array(32)));
function encode(bytes){return btoa(String.fromCharCode(...new Uint8Array(bytes))).replaceAll("+","-").replaceAll("/","_").replace(/=+$/,"");}
export const challenge=async raw=>encode(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(raw)));
export async function connect(ticket,verifier){
  const r=await fetch(API+"/auth/exchange",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({ticket,verifier}),credentials:"omit",redirect:"error",cache:"no-store",referrerPolicy:"no-referrer"});
  if(!r.ok) throw Error("This sign-in link has expired. Start again from Settings.");
  const session=await r.json();
  if(!/^[A-Za-z0-9_-]{43}$/.test(session.token)||!Number.isSafeInteger(session.user?.id)) throw Error("The sign-in service returned an invalid response.");
  await transaction("readwrite",store=>{
    // A fresh login always needs explicit opt-in, even on a shared browser.
    store.delete("base");
    store.put({token:session.token,user:session.user,expires:session.expires,tag:random(),enabled:false},"account");
  });
}
function bound(rec,tag) {
  if(!rec||rec.tag!==tag||rec.expires*1000<=Date.now()) throw Object.assign(Error("Your session has changed or expired. Sign in again."),{status:401});
  return rec;
}
async function api(rec,method,path,body){
  const init={method,credentials:"omit",redirect:"error",cache:"no-store",referrerPolicy:"no-referrer",
    signal:AbortSignal.timeout(25000),headers:{Authorization:"Bearer "+rec.token}};
  if(body!==undefined){init.headers["Content-Type"]="application/json";init.body=JSON.stringify(body);}
  const response=await fetch(API+path,init), data=await response.json();
  if(!response.ok) throw Object.assign(Error(data.error||"Cloud sync is unavailable."),{status:response.status});
  return data;
}
export async function call(op,text="{}"){
  // JSON is the boundary with Python; secrets never enter Flet controls or exports.
  try {
    const x=JSON.parse(text);
    if(op==="info"){
      const rec=await transaction("readonly",(_s,r)=>r);
      return JSON.stringify({ok:true,value:rec&&rec.expires*1000>Date.now()?{user:rec.user,tag:rec.tag,enabled:rec.enabled}:null});
    }
    if(op==="base"){
      let request;await transaction("readonly",(store,r)=>{bound(r,x.tag);request=store.get("base");});
      return JSON.stringify({ok:true,value:request.result||null});
    }
    if(op==="commit"){
      await transaction("readwrite",(store,r)=>{
        bound(r,x.tag);store.put({...r,enabled:true},"account");
        const q=store.get("base");
        q.onsuccess=()=>{if(!q.result || q.result.revision<=x.revision)store.put({revision:x.revision,workspace:x.workspace},"base");};
      });return '{"ok":true}';
    }
    if(op==="forget"){
      await transaction("readwrite",(store,r)=>{if(r?.tag===x.tag){store.delete("base");store.delete("account");}});
      return '{"ok":true}';
    }
    const rec=await transaction("readonly",(_s,r)=>bound(r,x.tag));
    const operations={read:["GET","/workspace"+(Number.isSafeInteger(x.since)&&x.since>0?"?since="+x.since:"")],write:["PUT","/workspace",x.body],logout:["DELETE","/session"],erase:["DELETE","/account"]};
    const args=operations[op];if(!args)throw Error("Unknown cloud action.");
    const value=await api(rec,...args);
    await transaction("readonly",(_s,r)=>bound(r,x.tag));
    return JSON.stringify({ok:true,value});
  } catch(e){return JSON.stringify({ok:false,status:e.status||0,error:e.status?e.message:"Could not reach cloud sync or browser storage. Retry when connected."});}
}
