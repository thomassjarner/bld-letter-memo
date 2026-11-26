"""Device-side coordination: locally durable saves first, version-checked writes."""
from core.messages import message, error_message
import asyncio
from data.cloud_client import CloudError
from data.cloud_merge import identify, merge, validate
from data.models import AppData


class CloudSync:
    def __init__(self, state, repo, client, schedule, safe=lambda:True):
        self.state, self.repo, self.client = state, repo, client
        self.schedule, self.safe = schedule, safe
        self.session = self.base = None
        self.revision = 0
        self.differences, self.choices = [], {}
        self.message = message('Keep a private copy of your training data across devices.')
        self.changed = self.applied = lambda: None
        self.lock = asyncio.Lock()
        self._scheduled = self._dirty = self._installing = False
        self.busy = self.consent = False
        self.ready = self.blocked = False

    async def initialize(self):
        try:
            self.session = await self.client.call("info")
            self.blocked = bool(self.session and self.repo.cloud_owner is not None
                                and self.repo.cloud_owner!=self.session["user"]["id"])
            if self.blocked:
                self.message = message('This browser holds another WCA account’s local workspace. Sign in with its owner, or use a separate browser profile for this account.')
            elif self.session and self.session["enabled"]:
                saved = await self.client.call("base",tag=self.session["tag"])
                if saved and self.repo.cloud_anchor == (self.session["user"]["id"],saved["revision"]):
                    self.base = validate(saved["workspace"])
                    self.revision = saved["revision"]
                    await self.repo.track_cloud(*self.repo.cloud_anchor)
                self.consent = True
            elif self.session:
                self.message = message('Signed in. Nothing from this browser has been uploaded.')
        except Exception as exc:
            self.message = error_message(exc) or message('Cloud sync is unavailable.')
        self.ready = True
        self.changed()
        if self.consent: await self.sync()

    def local_saved(self, status):
        if status == "Saved" and self.consent and not self._installing:
            self.request()

    def request(self):
        if not self.consent: return
        self._dirty = True
        if not self._scheduled:
            self._scheduled=True
            self.schedule(self._drain)

    async def _drain(self):
        try:
            while self._dirty:
                self._dirty=False
                await asyncio.sleep(.65)
                await self.sync()
        finally:
            self._scheduled=False

    async def enable(self):
        if self.session and not self.blocked:
            self.consent=True
            await self.sync()

    def later(self):
        self.differences=[]; self.choices={}
        if self.session and not self.session["enabled"]: self.consent=False
        self.message=message('Your device and cloud copies are unchanged.')
        self.changed()

    async def decide(self, which):
        if not self.differences or which not in ("device","cloud") or self.busy: return
        d=self.differences.pop(0)
        self.choices[d.path]=(d.device,d.cloud,which)
        if self.differences: self.changed()
        else: await self.sync()

    async def _forget(self, tag):
        try: await self.client.call("forget",tag=tag)
        finally:
            self.repo.stop_tracking_cloud()
            self.session=self.base=None
            self.revision=0
            self.differences=[]; self.choices={}
            self.consent=self._dirty=self.blocked=False

    async def disconnect(self, erase=False):
        async with self.lock:
            if not self.session: return
            tag=self.session["tag"]
            self.busy=True; self.changed()
            try:
                await self.client.call("erase" if erase else "logout",tag=tag)
                await self._forget(tag)
                self.message = (message('Cloud copy deleted; all devices signed out.') if erase else message('Signed out.'))+message(' Your local data is still here.')
            except CloudError as exc:
                if exc.status==401:
                    await self._forget(tag);self.message=message('Session ended. Your local data is still here.')
                elif not erase:
                    await self._forget(tag)
                    self.message=message('Signed out on this device. The offline session could not be revoked remotely.')
                else: self.message=message('The cloud deletion was not confirmed. Reconnect and try again.')
            except Exception:
                self.message=message('Could not finish disconnecting. Retry in Settings.')
            finally: self.busy=False; self.changed()

    async def sync(self):
        async with self.lock:
            if not self.session or not self.consent: return
            self.busy=True; self.changed()
            tag=self.session["tag"]
            try:
                for _ in range(3):
                    await self.repo.wait_saved()
                    response=await self.client.call("read",tag=tag,since=self.revision)
                    revision=response["revision"]
                    same = response.get("unchanged") is True
                    if same and (self.base is None or self.revision!=revision):
                        raise ValueError(message('Unexpected cloud version. Please retry.'))
                    remote=self.base if same else response["workspace"]
                    if type(revision) is not int or revision<0 or (revision==0)!=(remote is None):
                        raise ValueError(message('Unexpected cloud version. Your local data is unchanged.'))
                    if remote is not None and not same: remote=validate(remote)
                    await self.repo.wait_saved()
                    raw=self.state.data.to_dict()
                    if same and raw==self.base and self.session["enabled"]:
                        self.differences=[]; self.choices.clear()
                        self.message=message('Up to date · Saved on this device and in the cloud.')
                        return
                    device=identify(raw)
                    merged,diffs=merge(self.base,device,remote,self.choices) if remote is not None and not same else (device,[])
                    self.differences=diffs
                    if diffs:
                        self.message=message('Choose which edits to keep. Neither copy has been replaced.')
                        return
                    # Never swap schemes under a running timer, training round or editor.
                    if raw!=merged and not self.safe():
                        self.message=message('Cloud changes are ready. Open Settings to apply them.')
                        return
                    merged=validate(merged)
                    if remote!=merged:
                        try: result=await self.client.call("write",tag=tag,body={"revision":revision,"workspace":merged})
                        except CloudError as exc:
                            if exc.status==409: continue
                            raise
                        revision=result["revision"]
                    if self.state.data.to_dict()!=raw: continue
                    if raw!=merged and not self.safe():
                        self.message=message('Cloud changes are ready. Open Settings to apply them.')
                        return
                    if raw!=merged:
                        self._installing=True
                        try:
                            self.state.replace_data(AppData.from_dict(merged))
                            self.applied()
                            await self.repo.wait_saved()
                        finally: self._installing=False
                    await self.repo.track_cloud(self.session["user"]["id"],revision)
                    await self.client.call("commit",tag=tag,revision=revision,workspace=merged)
                    self.base,self.revision=merged,revision
                    self.session["enabled"]=True
                    self.choices.clear()
                    self.message=message('Up to date · Saved on this device and in the cloud.')
                    if self.state.data.to_dict()!=merged: self.request()
                    return
                self.message=message('Another device is still saving. Select Sync now to compare again.')
            except CloudError as exc:
                if exc.status==401:
                    await self._forget(tag)
                    self.message=message('Your session ended. Sign in again to sync this browser.')
                else: self.message=error_message(exc)
            except (ValueError,TypeError,KeyError,OSError) as exc:
                self.message=error_message(exc) or message('Cloud sync paused. Your local data is still here.')
            except Exception:
                self.message=message('Cloud sync is unavailable. Your local data is still here.')
            finally:
                self.busy=False; self.changed()
