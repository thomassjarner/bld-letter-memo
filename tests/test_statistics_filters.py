"""Exercise filter events through Flet's mounted session and serialized client patches."""
import asyncio
from copy import deepcopy

import msgpack
import pytest
from flet.controls.base_control import BaseControl
from flet.messaging.connection import Connection
from flet.messaging.protocol import ClientAction, configure_encode_object_for_msgpack
from flet.messaging.session import Session
from flet.pubsub.pubsub_hub import PubSubHub

from data.models import PracticeSolve, ProgressiveMemoAttempt
from test_navigation import MemoryRepository
from ui.pages.practice_page import PracticePage
from ui.pages.progressive_memo_page import ProgressiveMemoPage
from ui.state import AppState


async def exercise_filter_events(kind):
    conn = Connection()
    conn.loop = asyncio.get_running_loop()
    conn.pubsubhub = PubSubHub()
    pack = lambda obj: msgpack.packb(obj, default=configure_encode_object_for_msgpack(BaseControl))
    errors = []
    def send(msg):
        pack(msg)  # Actual transport snapshots are needed for the next *incremental* patch.
        if msg.action == ClientAction.SESSION_CRASHED:
            errors.append(str(msg.body))
    conn.send_message = send
    session = Session(conn)
    pack(session.get_page_patch())
    repo = MemoryRepository()
    repo.data.practice_solves = [PracticeSolve(31342,"U",i!=3) for i in range(5)]
    repo.data.progressive_memo_history = [ProgressiveMemoAttempt(str(i),"","","A" if i<4 else "B",
        {}, "CE","EC",1000+i,200,1,2) for i in range(5)]
    state = AppState(repo)
    before = deepcopy(repo.data.to_dict())
    if kind == "timer":
        activity = PracticePage(data=state)
        activity.show_timer(update=False)
    else:
        activity = ProgressiveMemoPage(data=state)
    activity.set_viewport(390,650)
    session.page.add(activity)
    async def choose(control, value, tab=False):
        session.apply_patch(control._i, {"selected":[value]} if tab else {"value":value})
        await session.dispatch_event(control._i, "change" if tab else "select", value)
        assert not errors, errors
    nav = activity.activity_header.picker
    await choose(nav,"stats",True)
    stats = activity.statistics
    stable = [nav, activity.body_host, stats, stats.filters, stats.filter_picker, stats.scope_picker, stats.window_picker,
              stats.scroll_area, stats.report, stats.recent, stats.accuracy.canvas, stats.timing.canvas]
    parents = [c.parent for c in stable]
    async def check():
        assert activity.body_host.content is stats and nav.selected == ["stats"]
        assert all(session.index.get(c._i) is c and c.parent is p for c,p in zip(stable,parents))
        assert not errors, errors
    assert stats.scope_picker.value == stats.window_picker.value == "all"
    for value in ("50","5","all"):
        await choose(stats.scope_picker,value)
        await check()
    for window in ("5","50","12","5"):
        await choose(stats.window_picker,window)
        await check()
        assert stats.report.visible and stats.window == int(window)
        for chart in (stats.accuracy,stats.timing):
            await session.dispatch_event(chart.canvas._i,"resize",{"w":250+int(window),"h":146})
            assert chart.width == 250+int(window)
            assert len(chart.canvas.shapes) >= 3
        if kind == "timer":
            assert stats.accuracy.headline.value == "20.0%"
            assert stats.metrics[1].value.value == "5:13.42" and stats.metrics[2].value.value == "—"
            assert [label.value for label in stats.odds.values] == ["0.67%","0.29%","0.03%"]
            assert stats.observed.values[1].value == "DNF" and stats.timing.headline.value == "5:13.42"
            await choose(stats.filter_picker,"Session 2")
            assert stats.empty.visible and not stats.report.visible
            await check()
            await choose(stats.filter_picker,"Session 1")
        else:
            for scheme in (":B","*"):
                await choose(stats.filter_picker,scheme)
                await choose(stats.phase_picker,"recall")
                assert stats.timing.headline.value == "2.00"
                await choose(stats.phase_picker,"memo")
                assert stats.timing.title.value == "Median memo time over time"
            await check()
    await choose(nav,"train",True)
    assert activity.body_host.content is activity.keyboard_listener and nav._i in session.index
    assert stats._i not in session.index
    await choose(nav,"stats",True)
    assert activity.statistics is stats and stats.window == 5 and stats.report.visible
    assert repo.data.to_dict() == before
    assert not errors, errors


@pytest.mark.parametrize("kind", ["timer","memo"])
def test_repeated_client_selections_resize_and_back_preserve_mounted_controls(kind):
    asyncio.run(exercise_filter_events(kind))
