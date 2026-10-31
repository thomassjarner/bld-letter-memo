"""Latest-position camera painting without pointer-event or full-viewer queues."""
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from test_navigation import no_client_mount
from ui.components.algorithm_cube import AlgorithmCube, TARGET_FPS


def event(x, y, dx=0, dy=0):
    return SimpleNamespace(local_position=SimpleNamespace(x=x, y=y),
                           local_delta=SimpleNamespace(x=dx, y=dy))


def test_drag_burst_draws_only_the_latest_position_on_the_canvas_and_keeps_the_caption():
    cube = AlgorithmCube()
    cube.load('R U')
    states, captions = cube.states, cube.move_text.spans
    page = SimpleNamespace(run_task=Mock())
    with patch.object(cube, '_page', return_value=page), patch.object(cube.canvas, 'update') as canvas_update, \
         patch.object(cube, 'update') as full_update, patch.object(cube, '_redraw', wraps=cube._redraw) as redraw:
        cube._drag_start(event(100, 80))
        for i in range(1, 121): cube._drag(event(100 + i * 2, 80 + i * .1, 999, 999))
        # The final position can arrive only on pan_end after client throttling.
        cube._drag_end(event(345, 93))
        assert cube.yaw == pytest.approx(-.62 + 2.45)
        assert cube.pitch == pytest.approx(.45 + .13)
        page.run_task.assert_called_once()
        redraw.assert_not_called()
        callback, revision = page.run_task.call_args.args
        asyncio.run(callback(revision))
        redraw.assert_called_once_with(update=False)
        canvas_update.assert_called_once()
        full_update.assert_not_called()
        assert not cube._drag_pending and not cube._drag_active
        cube._drag(event(900, 900))  # A late update from a released pointer is ignored.
        assert canvas_update.call_count == 1 and cube.yaw == pytest.approx(-.62 + 2.45)
    assert cube.states is states and cube.index == 0 and cube.move_text.spans is captions


def test_independent_drag_tasks_still_share_one_frame_rate_limit():
    cube = AlgorithmCube()
    page = SimpleNamespace(run_task=Mock())
    clock, paints = [0.0], []
    async def sleep(delay): clock[0] += delay
    def paint(update=True): paints.append(clock[0])
    with patch.object(cube, '_page', return_value=page), patch.object(cube.canvas, 'update'), \
         patch.object(cube, '_redraw', side_effect=paint), \
         patch('ui.components.algorithm_cube.time.perf_counter', side_effect=lambda: clock[0]), \
         patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        cube._drag_start(event(0, 0))
        for i in range(1, 7):
            clock[0] += .003
            cube._drag(event(i, 0))
            callback, revision = page.run_task.call_args.args
            asyncio.run(callback(revision))
        assert len(paints) == 6 and paints[0] == pytest.approx(.003)
        assert all(b - a >= 1 / TARGET_FPS - 1e-10 for a, b in zip(paints, paints[1:]))


def test_updates_arriving_between_frames_replace_the_pending_position_without_creating_more_tasks():
    cube = AlgorithmCube()
    page = SimpleNamespace(run_task=Mock())
    clock, paints = [0.0], []
    async def sleep(delay):
        clock[0] += delay
        if len(paints) == 1:
            for x in range(21, 81): cube._drag(event(x, 0))
            cube._drag_end(event(90, 0))
    def paint():
        paints.append(cube.yaw)
        if len(paints) == 1: cube._drag(event(20, 0))
    with patch.object(cube, '_page', return_value=page), patch.object(cube.canvas, 'update', side_effect=paint), \
         patch.object(cube, '_redraw'), patch('ui.components.algorithm_cube.time.perf_counter', side_effect=lambda: clock[0]), \
         patch('ui.components.algorithm_cube.asyncio.sleep', side_effect=sleep):
        cube._drag_start(event(0, 0))
        cube._drag(event(10, 0))
        callback, revision = page.run_task.call_args.args
        asyncio.run(callback(revision))
        assert paints == pytest.approx([-.52, .28])
        assert clock[0] == pytest.approx(1 / TARGET_FPS)
        page.run_task.assert_called_once()
        assert not cube._drag_pending and not cube._drag_dirty


@pytest.mark.parametrize('action', ['reset', 'view', 'load', 'seek', 'unmount'])
def test_queued_drag_frames_cannot_repaint_after_camera_reset_mode_change_case_change_seek_or_unmount(action):
    cube = AlgorithmCube()
    cube.load('R U')
    page = SimpleNamespace(run_task=Mock())
    with patch.object(cube, '_page', return_value=page), patch.object(cube.canvas, 'update') as canvas_update, \
         patch.object(cube, 'update'):
        cube._drag_start(event(0, 0))
        cube._drag(event(20, 10))
        callback, revision = page.run_task.call_args.args
        if action == 'reset': cube._reset_camera()
        elif action == 'view':
            cube.mode_picker.value = '2D'
            cube.mode_picker.on_select(None)
        elif action == 'load': cube.load('F D')
        elif action == 'seek': cube.seek(1)
        else: cube.will_unmount()
        camera = cube.yaw, cube.pitch
        asyncio.run(callback(revision))
        cube._drag(event(200, 100))
        canvas_update.assert_not_called()
        assert (cube.yaw, cube.pitch) == camera
        assert not cube._drag_pending and not cube._drag_active
        if action == 'reset': assert camera == (-.62, .45)


def test_replaced_gesture_keeps_its_own_task_when_an_older_task_exits():
    cube = AlgorithmCube()
    page = SimpleNamespace(run_task=Mock())
    with patch.object(cube, '_page', return_value=page), patch.object(cube.canvas, 'update') as canvas_update:
        cube._drag_start(event(0, 0)); cube._drag(event(10, 0))
        old_callback, old_revision = page.run_task.call_args.args
        cube._drag_start(event(100, 0)); cube._drag(event(110, 0))
        callback, revision = page.run_task.call_args.args
        asyncio.run(old_callback(old_revision))
        assert cube._drag_pending
        canvas_update.assert_not_called()
        asyncio.run(callback(revision))
        canvas_update.assert_called_once()
        assert cube.yaw == pytest.approx(-.42)


def test_dragging_during_playback_uses_animation_frames_and_can_continue_after_the_last_turn():
    cube = AlgorithmCube()
    cube.load('R')
    cube.playing, cube._moving = True, 'R'
    page = SimpleNamespace(run_task=Mock())
    with patch.object(cube, '_page', return_value=page), patch.object(cube, 'update'), \
         patch.object(cube.canvas, 'update') as canvas_update:
        cube._drag_start(event(0, 0)); cube._drag(event(10, 10))
        page.run_task.assert_not_called()
        cube._redraw()  # The existing animation frame paints the new camera.
        canvas_update.assert_called_once()
        cube.stop(keep_drag=True)
        cube._drag(event(20, 20))
        page.run_task.assert_called_once()
        assert cube.yaw == pytest.approx(-.42) and cube.pitch == pytest.approx(.65)


def test_2d_drag_is_ignored_and_detached_rendering_never_sends_updates():
    cube = AlgorithmCube()
    cube.mode_picker.value = '2D'
    with patch.object(cube.canvas, 'update') as canvas_update, patch.object(cube, '_redraw') as redraw:
        cube._drag_start(event(0, 0)); cube._drag(event(10, 10)); cube._drag_end(event(20, 20))
        redraw.assert_not_called()
        assert (cube.yaw, cube.pitch) == (-.62, .45)
        cube.mode_picker.value = '3D'
        cube._drag_start(event(0, 0))
        cube._drag(SimpleNamespace(local_delta=SimpleNamespace(x=10, y=1000)))
        redraw.assert_called_once_with(update=False)
        canvas_update.assert_not_called()
        assert cube.pitch == 1.2 and cube.yaw == pytest.approx(-.52)
