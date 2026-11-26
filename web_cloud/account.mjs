import {API} from "./cloud-endpoint.mjs";
import {challenge,connect,random} from "./cloud-store.mjs";
const key="bld-wca-signin:"+new URL(".",import.meta.url).pathname;
const chinese = {
  "Account · BLD Letter Memo": "账号 · BLD Letter Memo",
  "Sign in with WCA": "使用 WCA 账号登录",
  "Connecting to your WCA account…": "正在连接你的 WCA 账号…",
  "Return to the trainer": "返回训练区",
  "Cloud sync is not enabled for this site. Your local workspace is available as usual.": "本站尚未启用云同步，仍可正常使用本地数据。",
  "Sign-in cancelled. Your local data has not changed.": "已取消登录，本地数据未更改。",
  "Sign-in could not finish. Return to Settings and try again.": "未能完成登录，请返回“设置”重试。",
  "Please finish signing in from the same browser tab.": "请在开始登录的同一个浏览器标签页中完成登录。",
  "This sign-in link has expired. Start again from Settings.": "登录链接已过期，请返回“设置”重新登录。",
  "The sign-in service returned an invalid response.": "登录服务返回了无效的响应。",
  "Browser storage is unavailable.": "浏览器存储暂时不可用。",
  "Could not save the sync state on this device.": "未能在此设备上保存同步状态。",
  "Sign-in is unavailable. Return to the trainer to continue locally.": "暂时无法登录，返回训练区即可继续使用本地数据。"
};

export function accountLanguage(location, store){
  const query = new URLSearchParams(location.search);
  const returning = !!location.hash && location.hash.length > 1;
  let code = query.get("lang") === "zh-CN" ? "zh-CN" : "en";
  try {
    if (returning) code = store.getItem(key+":language") === "zh-CN" ? "zh-CN" : "en";
    else store.setItem(key+":language", code);
  } catch {} // Local login errors can still be displayed.
  return code;
}

export function accountCopy(source, code){
  return code === "zh-CN" ? (chinese[source] || chinese["Sign-in is unavailable. Return to the trainer to continue locally."]) : source;
}

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
if (typeof document !== "undefined") {
  let store;
  try { store = window.sessionStorage; } catch {}
  const code = accountLanguage(window.location, store);
  const copy = source => accountCopy(source, code);
  document.documentElement.lang = code;
  document.title = copy("Account · BLD Letter Memo");
  document.querySelector("h1").textContent = copy("Sign in with WCA");
  document.querySelector("a").textContent = copy("Return to the trainer");
  const status = document.getElementById("status");
  status.textContent = copy("Connecting to your WCA account…");
  handleLogin(window).catch(e => {
    status.textContent = copy(e.message || "Sign-in is unavailable. Return to the trainer to continue locally.");
  });
}
