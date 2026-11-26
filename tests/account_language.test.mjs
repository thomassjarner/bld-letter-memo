import test from "node:test";
import assert from "node:assert/strict";
import {mkdtemp,copyFile,writeFile,rm} from "node:fs/promises";
import {join} from "node:path";
import {tmpdir} from "node:os";
import {pathToFileURL} from "node:url";

test("the WCA handoff keeps the chosen language across its redirect, separately per tab",async()=>{
  const folder=await mkdtemp(join(tmpdir(),"bld-language-"));
  try {
    for(const file of ["cloud-store.mjs","account.mjs"])
      await copyFile(new URL("../web_cloud/"+file,import.meta.url),join(folder,file));
    await writeFile(join(folder,"cloud-endpoint.mjs"),'export const API="https://example.invalid";');
    const {accountLanguage,accountCopy}=await import(pathToFileURL(join(folder,"account.mjs")));
    const values=new Map(), store={getItem:k=>values.get(k),setItem:(k,v)=>values.set(k,v)};
    assert.equal(accountLanguage({search:"?lang=zh-CN",hash:""},store),"zh-CN");
    assert.equal(accountLanguage({search:"",hash:"#error=cancelled"},store),"zh-CN");
    assert.equal(accountCopy("Sign in with WCA","zh-CN"),"使用 WCA 账号登录");
    assert.equal(accountCopy("Sign-in cancelled. Your local data has not changed.","zh-CN"),"已取消登录，本地数据未更改。");
    assert.equal(accountLanguage({search:"",hash:""},store),"en");
    assert.equal(accountCopy("Sign in with WCA","en"),"Sign in with WCA");
  } finally {await rm(folder,{recursive:true,force:true});}
});
