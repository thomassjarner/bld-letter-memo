// WCA authenticates a user; only this service stores their private workspace.
const WCA = "https://www.worldcubeassociation.org";
const TICKET_AGE = 120, FLOW_AGE = 600, SESSION_AGE = 30 * 86400;
const RAW_LIMIT = 8 * 1024 * 1024, STORED_LIMIT = 1750000;
const cookie = "__Host-bld-login";
const seal = "Path=/; Secure; HttpOnly; SameSite=Lax";
const proofFormat = /^[A-Za-z0-9_-]{43}$/;
const now = () => Math.floor(Date.now() / 1000);
const enc = new TextEncoder();
const base64 = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes))).replaceAll("+","-").replaceAll("/","_").replace(/=+$/,"");
const random = () => base64(crypto.getRandomValues(new Uint8Array(32)));
const hash = async text => base64(await crypto.subtle.digest("SHA-256", enc.encode(text)));
const common = {"Cache-Control":"no-store", "Referrer-Policy":"no-referrer", "X-Content-Type-Options":"nosniff", "Content-Security-Policy":"default-src 'none'; frame-ancestors 'none'"};
class Failure extends Error { constructor(status, msg) { super(msg); this.status = status; } }
function json(body, status=200, headers={}) {
  return new Response(JSON.stringify(body), {status, headers:{...common, ...headers, "Content-Type":"application/json; charset=utf-8"}});
}
function redirect(to, value) {
  return new Response(null, {status:303, headers:{...common, Location:String(to), "Set-Cookie":cookie+"="+value}});
}
function setup(env) {
  let app;
  try { app = new URL(env.APP_URL); } catch {}
  if (!app || app.protocol !== "https:" || app.username || app.password || app.search || app.hash ||
      !app.pathname.endsWith("/") || !env.DB || !env.WCA_CLIENT_SECRET || !env.WCA_CLIENT_ID ||
      env.WCA_CLIENT_ID.startsWith("replace-")) throw new Failure(503,"Cloud sync is not configured.");
  return app;
}
async function bounded(req, limit) {
  if (Number(req.headers.get("Content-Length") || 0)>limit) throw new Failure(413,"This workspace is too large to sync. Your local copy is unchanged.");
  if (!req.headers.get("Content-Type")?.toLowerCase().startsWith("application/json") || !req.body) throw new Failure(400,"Expected JSON.");
  const reader=req.body.getReader(); const chunks=[]; let len=0;
  while(true) {
    const {done,value}=await reader.read(); if(done) break;
    len+=value.byteLength;
    if(len>limit) {await reader.cancel(); throw new Failure(413,"This workspace is too large to sync. Your local copy is unchanged.");}
    chunks.push(value);
  }
  try {return JSON.parse(await new Blob(chunks).text());} catch {throw new Failure(400,"Invalid JSON.");}
}
function statement(env,sql,...args){return env.DB.prepare(sql).bind(...args);}
async function cleanup(env){
  const n=now();
  await env.DB.batch(["oauth_flows","tickets","sessions"].map(t=>statement(env,"DELETE FROM "+t+" WHERE expires<=?",n)));
}
async function start(req,env,url) {
  const browser=url.searchParams.get("state")||"", challenge=url.searchParams.get("challenge")||"";
  if(!proofFormat.test(browser)||!proofFormat.test(challenge)) throw new Failure(400,"Start sign-in from BLD Letter Memo.");
  const state=random(), browserCookie=random(), proof=random();
  // Bind the provider return to this top-level browser and a second proof to
  // the exact app tab that will receive the short-lived handoff.
  await statement(env,"INSERT INTO oauth_flows VALUES(?,?,?,?,?)",await hash(state+"."+browserCookie),browser,challenge,proof,now()+FLOW_AGE).run();
  const to=new URL("/oauth/authorize",WCA);
  to.search=new URLSearchParams({client_id:env.WCA_CLIENT_ID,response_type:"code",scope:"public",state,
    redirect_uri:new URL("/auth/callback",url).href,code_challenge_method:"S256",code_challenge:await hash(proof)});
  return redirect(to,browserCookie+"; "+seal+"; Max-Age="+FLOW_AGE);
}
async function callback(req,env,url,app,fetcher){
  const to=new URL("account.html",app);
  const finish = args => {to.hash=new URLSearchParams(args).toString(); return redirect(to,"; "+seal+"; Max-Age=0");};
  const browserCookie=(req.headers.get("Cookie")||"").split(/;\s*/).find(v=>v.startsWith(cookie+"="))?.slice(cookie.length+1)||"";
  const state=url.searchParams.get("state")||"";
  if(!proofFormat.test(state)||!proofFormat.test(browserCookie)) return finish({error:"expired"});
  const flow=await statement(env,"DELETE FROM oauth_flows WHERE state=? AND expires>? RETURNING *",await hash(state+"."+browserCookie),now()).first();
  if(!flow) return finish({error:"expired"});
  if(url.searchParams.has("error")) return finish({error:"cancelled",state:flow.browser});
  const code=url.searchParams.get("code");
  if(!code||code.length>1024) return finish({error:"expired",state:flow.browser});
  try {
    const token=await fetcher(WCA+"/oauth/token",{method:"POST",redirect:"error",headers:{Accept:"application/json"},
      body:new URLSearchParams({grant_type:"authorization_code",client_id:env.WCA_CLIENT_ID,client_secret:env.WCA_CLIENT_SECRET,
        redirect_uri:new URL("/auth/callback",url).href,code,code_verifier:flow.proof})});
    if(!token.ok) throw Error();
    const access=(await token.json()).access_token;
    if(typeof access!=="string" || !access) throw Error();
    const profile=await fetcher(WCA+"/api/v0/me",{redirect:"error",headers:{Authorization:"Bearer "+access,Accept:"application/json"}});
    if(!profile.ok) throw Error();
    const {me}=await profile.json();
    if(!Number.isSafeInteger(me?.id) || me.id<1) throw Error();
    const ticket=random();
    await statement(env,"INSERT INTO tickets VALUES(?,?,?,?,?,?)",await hash(ticket),flow.challenge,me.id,
      String(me.name||"WCA account").slice(0,128),String(me.wca_id||"").slice(0,32),now()+TICKET_AGE).run();
    return finish({ticket,state:flow.browser});
  } catch {return finish({error:"unavailable",state:flow.browser});}
}
async function exchange(req,env) {
  const body=await bounded(req,1024);
  if(!proofFormat.test(body?.ticket||"")||!proofFormat.test(body?.verifier||"")) throw new Failure(400,"Sign in again.");
  const row=await statement(env,"DELETE FROM tickets WHERE ticket=? AND challenge=? AND expires>? RETURNING account,name,wca_id",
    await hash(body.ticket),await hash(body.verifier),now()).first();
  if(!row) throw new Failure(401,"Sign-in expired. Start again.");
  const token=random(),expires=now()+SESSION_AGE;
  await statement(env,"INSERT INTO sessions VALUES(?,?,?)",await hash(token),row.account,expires).run();
  return json({token,expires,user:{id:row.account,name:row.name,wca_id:row.wca_id}});
}
async function loadAccount(req,env) {
  const raw=req.headers.get("Authorization")?.match(/^Bearer ([A-Za-z0-9_-]{43})$/)?.[1];
  if(!raw) throw new Failure(401,"Please sign in again.");
  const key=await hash(raw);
  const row=await statement(env,"SELECT account FROM sessions WHERE token=? AND expires>?",key,now()).first();
  if(!row) throw new Failure(401,"Please sign in again.");
  return {id:row.account,key};
}
async function workspace(req,env,who) {
  if(req.method==="GET"){
    const since=new URL(req.url).searchParams.get("since");
    if(since && /^[1-9][0-9]{0,14}$/.test(since)){
      const head=await statement(env,"SELECT revision FROM workspaces WHERE account=?",who.id).first();
      if(head?.revision===Number(since)) return json({revision:head.revision,unchanged:true});
    }
    const row=await statement(env,"SELECT revision,payload FROM workspaces WHERE account=?",who.id).first();
    if(!row) return json({revision:0,workspace:null});
    // D1 may return BLOBs as an array or an ArrayBuffer, depending on the driver.
    const blob=new Blob([new Uint8Array(row.payload)]);
    const text=await new Response(blob.stream().pipeThrough(new DecompressionStream("gzip"))).text();
    return new Response('{"revision":'+row.revision+',"workspace":'+text+'}',{headers:{...common,"Content-Type":"application/json; charset=utf-8"}});
  }
  if(req.method!=="PUT") throw new Failure(405,"Method not allowed.");
  const body=await bounded(req,RAW_LIMIT);
  const {revision,workspace:ws}=body||{};
  if(!Number.isSafeInteger(revision)||revision<0||!ws||ws.version!==18||
     !ws.schemes||typeof ws.schemes!=="object"||Array.isArray(ws.schemes)||
     !ws.practice_sessions||typeof ws.practice_sessions!=="object"||Array.isArray(ws.practice_sessions)||
     !ws.global_words||typeof ws.global_words!=="object"||Array.isArray(ws.global_words)) throw new Failure(422,"Unsupported workspace. Nothing was replaced.");
  const bytes=await new Response(new Blob([JSON.stringify(ws)]).stream().pipeThrough(new CompressionStream("gzip"))).arrayBuffer();
  if(bytes.byteLength>STORED_LIMIT) throw new Failure(413,"This workspace is too large to sync. Your local copy is unchanged.");
  // Recheck the session in the same write (also protects in-flight writes
  // racing a sign-out/deletion); never accept an account ID from the browser.
  const result=revision===0
    ? await statement(env,"INSERT INTO workspaces(account,revision,payload) SELECT account,1,? FROM sessions WHERE token=? AND expires>? ON CONFLICT(account) DO NOTHING",bytes,who.key,now()).run()
    : await statement(env,"UPDATE workspaces SET revision=revision+1,payload=? WHERE account=? AND revision=? AND EXISTS(SELECT 1 FROM sessions WHERE token=? AND expires>?)",bytes,who.id,revision,who.key,now()).run();
  if(result.meta.changes!==1) throw new Failure(409,"The cloud copy changed. Compare the latest copy before saving.");
  return json({revision:revision+1});
}
export async function handle(req,env,fetcher=fetch) {
  let cors={};
  try {
    const app=setup(env), url=new URL(req.url), path=url.pathname;
    if(req.method==="GET" && path==="/auth/start") {
      if(env.LOGIN_LIMIT && !(await env.LOGIN_LIMIT.limit({key:"start:"+String(req.headers.get("CF-Connecting-IP")||"unknown")})).success)
        throw new Failure(429,"Too many sign-ins. Wait a minute and try again.");
      return await start(req,env,url);
    }
    if(req.method==="GET" && path==="/auth/callback") return await callback(req,env,url,app,fetcher);
    if(req.headers.get("Origin")!==app.origin) throw new Failure(403,"Open BLD Letter Memo to use this service.");
    cors={"Access-Control-Allow-Origin":app.origin,Vary:"Origin"};
    if(req.method==="OPTIONS") return new Response(null,{status:204,headers:{...common,...cors,
      "Access-Control-Allow-Headers":"Authorization, Content-Type","Access-Control-Allow-Methods":"GET, POST, PUT, DELETE, OPTIONS","Access-Control-Max-Age":"600"}});
    let response;
    if(req.method==="POST" && path==="/auth/exchange") response=await exchange(req,env);
    else {
      const who=await loadAccount(req,env);
      if(path==="/workspace") response=await workspace(req,env,who);
      else if(path==="/session" && req.method==="DELETE"){
        await statement(env,"DELETE FROM sessions WHERE token=?",who.key).run(); response=json({ok:true});
      } else if(path==="/account" && req.method==="DELETE"){
        await env.DB.batch([statement(env,"DELETE FROM workspaces WHERE account=?",who.id),
          statement(env,"DELETE FROM tickets WHERE account=?",who.id),statement(env,"DELETE FROM sessions WHERE account=?",who.id)]);
        response=json({ok:true});
      } else throw new Failure(404,"Unknown request.");
    }
    for(const [k,v] of Object.entries(cors)) response.headers.set(k,v);
    return response;
  } catch(e){return json({error:e instanceof Failure?e.message:"The sync service is unavailable. Please retry."},e instanceof Failure?e.status:503,cors);}
}
export default {fetch:(req,env)=>handle(req,env),scheduled:(_event,env,ctx)=>ctx.waitUntil(cleanup(env))};
