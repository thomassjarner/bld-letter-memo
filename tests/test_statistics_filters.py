"""Exercise filter events through Flet's mounted session and serialized client patches."""
import asyncio
from copy import deepcopy

import msgpack
import pytest
import flet as ft
from flet.controls.base_control import BaseControl
from flet.messaging.connection import Connection
from flet.messaging.protocol import ClientAction, configure_encode_object_for_msgpack
from flet.messaging.session import Session
from flet.pubsub.pubsub_hub import PubSubHub

from core.training_statistics import Attempt, summarize
from data.models import PracticeSolve, ProgressiveMemoAttempt
from test_navigation import MemoryRepository
from ui.components.trend_chart import TrendChart
from ui.pages.practice_page import PracticePage
from ui.pages.progressive_memo_page import ProgressiveMemoPage
from ui.state import AppState


def pointer(x):
    pos={"x":x,"y":62}
    return dict(k="mouse", l=pos, g=pos, ts={"microseconds":1},
        **dict.fromkeys("dev ps pMin pMax dist distMax size rMj rMn rMin rMax or tilt".split(),0))


async def exercise_filter_events(kind):
    conn = Connection()
    conn.loop = asyncio.get_running_loop()
    conn.pubsubhub = PubSubHub()
    pack = lambda obj: msgpack.packb(obj, default=configure_encode_object_for_msgpack(BaseControl))
    errors, messages = [], []
    def send(msg):
        pack(msg)  # Actual transport snapshots are needed for the next *incremental* patch.
        messages.append(msg.action)
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
              stats.scroll_area, stats.report, stats.recent, stats.accuracy.canvas, stats.timing.canvas,
              stats.timing.inspector, stats.timing.guide, stats.timing.description]
    parents = [c.parent for c in stable]
    async def check():
        assert activity.body_host.content is stats and nav.selected == ["stats"]
        assert all(session.index.get(c._i) is c and c.parent is p for c,p in zip(stable,parents))
        assert not errors, errors
    assert stats.scope_picker.value == stats.window_picker.value == "all"
    # The report, not the charts or the sticky filters, owns the scrolling.
    assert isinstance(stats.scroll_area,ft.ListView) and stats.scroll_area.scroll.interactive
    assert stats.report.scroll is None and not stats.scroll_area.auto_scroll
    for w,h in ((280,370),(1440,780),(390,650)):
        activity.set_viewport(w,h)
        activity.update()
        assert stats.width == w and stats.height == activity.body_host.height
        assert stats.filters.height+stats.spacing+stats.scroll_area.height == h-activity.activity_header.view.height-activity.spacing
        assert stats.scroll_area.width == w and stats.scroll_area.height < h
        assert stats.filter_picker.width+stats.filters.spacing+stats.scope_picker.width <= w
        await check()
    c = stats.timing
    await session.dispatch_event(c.canvas._i,"resize",{"w":250,"h":146})
    assert c.inspector.on_scroll is c.inspector.on_pan_update is c.inspector.on_vertical_drag_update is None
    shapes = c.canvas.shapes
    await session.dispatch_event(c.inspector._i,"hover",pointer(185))
    assert c.guide.opacity and c.selected_index==3 and c.guide.left==pytest.approx(184.25)
    assert c.description.value.startswith("#4 · 5:13.42" if kind=="timer" else "#4 · 12.03")
    assert "Cumulative:" in c.description.value
    prior=len(messages)
    await session.dispatch_event(c.inspector._i,"hover",pointer(184))
    assert len(messages)==prior and c.canvas.shapes is shapes
    await session.dispatch_event(c.inspector._i,"exit",pointer(252))
    assert c.guide.opacity==0 and "Hover or tap" in c.description.value
    await session.dispatch_event(c.inspector._i,"tap_up",{"k":"touch","l":{"x":-1,"y":20}})
    assert c.selected_index==0 and c.description.value.startswith("#1 · DNF (5:13.42)" if kind=="timer" else "#1 · 12.00")
    assert c.canvas.shapes is shapes
    for value in ("50","5","all"):
        await choose(stats.scope_picker,value)
        await check()
        assert c.selected_index is None
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
            assert [label.value for label in stats.odds.values] == ["0.76%","0.33%","0.04%"]
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
    if kind=="timer":
        field=stats.goal_field
        async def enter(value,submit):
            session.apply_patch(field._i,{"value":value})
            await session.dispatch_event(field._i,"change",value)
            assert not field.error
            if submit:
                await session.dispatch_event(field._i,"submit",value)
        await enter("1:60",True)
        assert field.error and stats.goal_result.value==""
        await enter("6:00.00",False)
        assert "Check odds" in stats.goal_result.value
        await session.dispatch_event(stats.goal_button._i,"click",{})
        assert "Under 6:00.00 · Single: 20.7%" in stats.goal_result.value
        assert "Valid Ao5: Need 3 successful times" in stats.goal_result.value
        await choose(stats.filter_picker,"Session 2")
        assert stats.empty.visible and not stats.goal_result.value
        await choose(stats.filter_picker,"Session 1")
        assert "Single: 20.7%" in stats.goal_result.value
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


def test_group_marks_describe_what_was_plotted_without_implying_one_solve():
    rows = [Attempt(1,1,9000) if i%2==0 else Attempt(0,1,None) for i in range(201)]
    points = summarize(rows,5,offset=100).points
    chart = TrendChart(False,True,None)
    chart.set_series("Time","","",points,5)
    assert chart.numbers[:2]==[101,103]
    assert chart._readout(1)=="#102–103 · Median 1:30.00 · 1 DNF\nRolling 5: 1:30.00"
    assert all(chart._nearest(chart._x(i))==i for i in range(len(points)))
    assert chart._nearest(-100)==0 and chart._nearest(chart.width+100)==len(points)-1
    chart = TrendChart(True,True,None)
    chart.set_series("Accuracy","","",points,5)
    assert chart._readout(1)=="#102–103 · 50.0% · 1/2\nRolling 5: 66.7%"


def test_singleton_penalty_and_unscored_memo_readouts():
    points = summarize([Attempt(1,1,8102,True)],offset=11).points
    for percent in (False,True):
        chart=TrendChart(percent,True,None)
        chart.set_series("","","",points)
        assert "#12" in chart._readout(0) and "1:21.02 (+2)" in chart._readout(0)
        assert chart._nearest(0)==chart._nearest(1000)==0 and chart._x(0)==chart.width/2
    chart = TrendChart(True,False,None)
    chart.set_series("","","",summarize([Attempt(0,0,2000)]).points)
    assert chart._readout(0)=="#1 · — · 0/0 letters\nCumulative: —"
