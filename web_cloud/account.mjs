import {API} from "./cloud-endpoint.mjs";
import {challenge,connect,random} from "./cloud-store.mjs";
const key="bld-wca-signin:"+new URL(".",import.meta.url).pathname;
export async function handleLogin({location,history,sessionStorage},finish=connect){
  if(!API)throw Error("Cloud sync is not enabled for this site. Your local workspace is available as usual.");
  const result=new URLSearchParams(location.hash.slice(1));
  if(result.size){
    // Remove one-time handoff parameters immediately. No third-party assets on this page.
    history.replaceState(null,"",location.pathname);
    const saved=JSON.parse(sessionStorage.getItem(key)||"null");sessionStorage.removeItem(key);
    if(result.has("error")){
      if(result.get("error")==="cancelled")throw Error("Sign-in cancelled. Your local data has not changed.");
      throw Error("Sign-in could not finish. Return to Settings and try again.");
    }
    if(!saved||saved.until<Date.now()||saved.state!==result.get("state"))throw Error("Please finish signing in from the same browser tab.");
    await finish(result.get("ticket"),saved.proof);
    location.replace(new URL("./#/account",import.meta.url));return;
  }
  const state=random(),proof=random();
  sessionStorage.setItem(key,JSON.stringify({state,proof,until:Date.now()+10*60*1000}));
  const to=new URL("/auth/start",API);to.search=new URLSearchParams({state,challenge:await challenge(proof)});
  location.replace(to.href);
}
if(typeof document!=="undefined") handleLogin(window).catch(e=>{
  document.getElementById("status").textContent=e.message||"Sign-in is unavailable. Return to the trainer to continue locally.";
});
