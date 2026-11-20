"""Optional adapter for the static Flet/Pyodide build. No desktop dependencies."""
import json
import sys
from urllib.parse import urljoin, urlsplit
from data.cloud_endpoint import SYNC_URL


class CloudError(Exception):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class BrowserCloud:
    def __init__(self, module, site, returning):
        self.module = module
        self.login_url = urljoin(site, "account.html")
        self.returning = returning

    @classmethod
    async def open(cls):
        if not SYNC_URL or sys.platform != "emscripten":
            return None
        import flet_js
        from pyodide.code import run_js
        from js import location
        # Resolve against the shipped Python worker, never a user query or hash.
        site = urljoin(str(location.href), ".")
        module = await run_js("(url) => import(url)")(urljoin(site,"cloud-store.mjs"))
        returning = urlsplit(str(flet_js.documentUrl)).fragment == "/account"
        return cls(module,site,returning)

    async def call(self, op, **args):
        result=json.loads(str(await self.module.call(op,json.dumps(args,ensure_ascii=False,separators=(",",":")))))
        if not result.get("ok"):
            raise CloudError(result.get("error") or "Cloud sync is unavailable.",result.get("status",0))
        return result.get("value")
