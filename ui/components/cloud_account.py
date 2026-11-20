"""Compact Settings panel for optional workspace sync."""
import flet as ft
from data.cloud_merge import Difference
from ui.design import action_button, panel, section_title
from ui.theme_colors import show_themed_dialog


class AccountPanel:
    def __init__(self, owner):
        self.owner=owner
        self.cloud=None
        self.unavailable="Cloud sync hasn’t been enabled for this site. You can still save locally and export a backup."
        self.body=ft.Column(spacing=9,tight=True)
        self.control=panel(self.body)
        self.render()

    @staticmethod
    def text(s,muted=True):
        return ft.Text(s,size=13,color=ft.Colors.ON_SURFACE_VARIANT if muted else ft.Colors.ON_SURFACE,selectable=True)

    def render(self,update=False):
        c=self.cloud
        rows=[section_title("Account & sync",ft.Icons.CLOUD_OUTLINED)]
        if not c:
            rows.append(self.text(self.unavailable))
        elif not c.ready:
            rows.append(self.text("Checking this device…"))
        elif not c.session:
            rows.extend([self.text(c.message),
                action_button("Sign in with WCA",primary=True,icon=ft.Icons.LOGIN,
                              url=ft.Url(c.client.login_url,target=ft.UrlTarget.SELF))])
        else:
            user=c.session["user"];name=user["name"] + (" · "+user["wca_id"] if user.get("wca_id") else "")
            rows.extend([self.text(name,False),self.text("Syncing…" if c.busy else c.message)])
            if c.blocked:
                pass  # Offer sign-out below; never transfer another account’s local data.
            elif c.differences:
                d=c.differences[0]
                rows.extend([self.text(f"{d.label} · {len(c.differences)} to review",False)])
                for label,side,value in (("This device","device",d.device),("Cloud","cloud",d.cloud)):
                    description=Difference.describe(value)
                    rows.append(ft.Column([ft.Text(label,size=12,weight=ft.FontWeight.W_600),
                        ft.Container(ft.Column([self.text(description,False)],scroll=ft.ScrollMode.AUTO,
                                               tight=True),height=70 if len(description)>100 else None),
                        ft.OutlinedButton("Keep "+label.lower(),on_click=self._decision(c,side),disabled=c.busy)
                    ],spacing=4,tight=True))
                rows.append(ft.TextButton("Decide later",on_click=lambda _:c.later(),disabled=c.busy))
            elif not c.session["enabled"]:
                rows.extend([self.text("Combine the schemes, pairs, algorithms, settings and history on this browser with this WCA account. Only link a browser whose data belongs to you."),
                    action_button("Enable sync",primary=True,icon=ft.Icons.CLOUD_SYNC_OUTLINED,
                                  on_click=self._action(c.enable),disabled=c.busy)])
            else:
                rows.append(action_button("Sync now",icon=ft.Icons.SYNC,on_click=self._action(c.sync),disabled=c.busy))
            actions=[ft.TextButton("Sign out",on_click=self._action(c.disconnect),disabled=c.busy)]
            if c.session["enabled"] and not c.blocked:
                actions.append(ft.TextButton("Delete cloud copy…",on_click=self._confirm_delete,disabled=c.busy))
            rows.append(ft.Row(actions,spacing=6,wrap=True))
        self.body.controls=rows
        if update: self.owner.update()

    @staticmethod
    def _action(callback):
        async def go(_): await callback()
        return go

    @staticmethod
    def _decision(c,side):
        async def go(_): await c.decide(side)
        return go

    def _confirm_delete(self,_):
        c=self.cloud
        if not c or not c.session: return
        tag=c.session["tag"]
        def cancel(_): self.owner.page.pop_dialog()
        async def remove(_):
            self.owner.page.pop_dialog()
            if c.session and c.session["tag"]==tag: await c.disconnect(erase=True)
        dialog=ft.AlertDialog(modal=True,title=ft.Text("Delete your cloud copy?"),
            content=ft.Text("This removes the training workspace stored for this WCA account and signs out all devices. The local copies and your WCA account are kept."),
            actions=[ft.TextButton("Cancel",on_click=cancel),ft.OutlinedButton("Delete cloud copy",on_click=remove)])
        d=self.owner.state.data
        show_themed_dialog(self.owner.page,dialog,d.dark_mode,d.light_theme)
