"""Repaint fidelity, timeline behavior and direct study routes."""
from copy import deepcopy
from math import cos, sin, pi
from unittest.mock import patch

import flet as ft
import msgpack
import pytest
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack

from core.algorithms import algorithm_states, move_spec, parse_algorithm
from test_case_library import open_library
from test_navigation import click_nav, no_client_mount, walk
from ui.components.algorithm_cube import AlgorithmCube
from ui.components.cube_projection import project_cube


def _wire(obj):
    return msgpack.unpackb(msgpack.packb(obj, default=configure_encode_object_for_msgpack(ft.Control)), raw=False)


def _apply_operations(client, operations):
    def locate(path):
        node = client
        for part in path[:-1]: node = node[part]
        return node, path[-1]

    for op in operations:
        action = op['op']
        if action == 'move':
            src, key = locate(op['from'])
            value = src.pop(key)
        else:
            value = op.get('value')
        target, key = locate(op['path'])
        if action in ('add','move') and isinstance(target,list): target.insert(key,value)
        elif action == 'remove':
            if isinstance(target,list): target.pop(key)
            else: target.pop(key, None)
        else: target[key] = value


def test_canvas_patches_reconstruct_the_drawing_when_faces_enter_leave_and_change_order():
    cube = AlgorithmCube()
    cube.load("[R, U' L' U]", targets=('BUR','BUL'))
    canvas = cube.canvas
    client = _wire(canvas)
    ObjectPatch.from_diff(canvas,canvas,control_cls=BaseControl)
    # Reconstruct the serialized drawing as a client receives it, including
    # edits inside retained paths, label removal, complete scene reorder and
    # moving from the 54-sticker net back to a different 3D camera.
    for yaw, pitch, turn, view, letters in [
        (-.58,.45,None,'3D',True), (.8,-.6,'Fw','3D',False), (2.8,.3,'M','3D',True),
        (.12,-.3,("U","D'"),'3D',True), (.12,-.3,None,'2D',False),
        (-2.3,-.6,None,'3D',True), (-.62,.45,None,'3D',True)]:
        cube.yaw,cube.pitch,cube._moving,cube._fraction = yaw,pitch,turn,.41
        cube.mode_picker.value,cube.letter_switch.value = view,letters
        cube._redraw(update=False)
        delta, added, removed = ObjectPatch.from_diff(canvas,canvas,control_cls=BaseControl)
        if yaw == -.58:
            assert not added and not removed  # camera pan only; no shape churn
        _apply_operations(client, _wire(delta.patch))
        assert client['shapes'] == _wire(canvas)['shapes']


@pytest.mark.parametrize('moves', [('R',), ("Fw'",), ('M',), ('y',), ('D2',"U'")])
def test_midturn_sticker_centres_match_independent_rotation_in_world_coordinates(moves):
    state = algorithm_states(parse_algorithm("B U2 R F' L"))[-1]
    yaw,pitch,fraction = 1.12,-.42,.37
    tiles = project_cube(state,480,350,yaw=yaw,pitch=pitch,moving=moves,fraction=fraction)
    labels = {t.label:t.points for t in tiles if t.label}
    # Rodrigues' formula operates on world positions, independently of the
    # projection's block templates, camera composition and depth ordering.
    def spin(v, axis, angle):
        n = tuple(float(i == 'xyz'.index(axis)) for i in range(3))
        x,y,z=v; a,b,c=n
        cross=(b*z-c*y,c*x-a*z,a*y-b*x); dot=a*x+b*y+c*z
        return tuple(m*cos(angle)+k*sin(angle)+d*dot*(1-cos(angle)) for m,k,d in zip(v,cross,n))
    def camera(v):
        x,y,z=spin(v,'y',yaw)
        return x, y*cos(pitch)-z*sin(pitch), y*sin(pitch)+z*cos(pitch)
    seen=set()
    for (p,n), home in state.items():
        if len(home)==1 or set(home)==set('UFR'): continue
        centre = tuple(2*a/3 + b*(1/3+.003) for a,b in zip(p,n))
        for move in moves:
            axis,layers,q=move_spec(move)
            if p['xyz'.index(axis)] in layers:
                centre=spin(centre,axis,q*pi/2*fraction); n=spin(n,axis,q*pi/2*fraction)
                break
        if camera(n)[2] <= .001: continue
        x,y,_=camera(centre)
        corners=labels[home]
        assert tuple(sum(p[i] for p in corners)/4 for i in (0,1)) == pytest.approx((240+x*350*.285,175-y*350*.285))
        seen.add(home)
    assert seen == set(labels)-{'★','●'}


def test_seek_from_visible_move_pauses_at_its_start_and_stale_or_hidden_links_do_nothing():
    cube=AlgorithmCube()
    cube.set_simultaneous_moves(True)
    cube.load("R U D' L")
    grouped=cube.move_text.spans[1]
    cube.seek(4);cube.playing=True
    grouped.on_click(None)
    assert not cube.playing and cube.index==1 and cube.states[1]==algorithm_states(parse_algorithm('R'))[-1]
    assert cube.move_text.spans[1].style.decoration==ft.TextDecoration.UNDERLINE
    cube.set_sequence_visible(False);cube.seek(0);grouped.on_click(None)
    assert not cube.track.visible and cube.index==0
    cube.load('F B D');cube.set_sequence_visible(True)
    grouped.on_click(None)
    assert cube.index==0
    cube.move_text.spans[-1].on_click(None)
    assert cube.index==2


def test_reset_view_is_available_below_the_cube_and_keeps_the_current_move_and_view_choices():
    cube=AlgorithmCube();cube.load("[R,U]");cube.seek(2);cube.yaw=1.4;cube.pitch=-.2
    cube.letter_switch.value=False
    assert cube.reset_view in list(walk(cube.display_switches))
    cube.reset_view.on_click(None)
    assert cube.index==2 and not cube.letter_switch.value and (cube.yaw,cube.pitch)==(-.62,.45)
    cube.mode_picker.value='2D';cube._change_view_mode()
    assert not cube.reset_view.visible
    cube.mode_picker.value='3D';cube._change_view_mode()
    assert cube.reset_view.visible


def test_scheme_target_filters_and_clear_preserve_the_selected_case_and_editor_draft():
    _,repo,_,view = open_library()
    view.scheme.corners.stickers['UBL']='Æ'
    view._render_list()
    assert next(o for o in view.first_target.options if o.key=='UBL').text=='Æ · UBL'
    assert next(o for o in view.second_target.options if o.key=='UBL').text=='Æ · UBL'
    before=deepcopy(repo.data.to_dict())
    key=view.selected_case;draft=view.case_converter.source+" R R'"
    view.case_converter.load(draft,notify=True);view.first_target.value='UBL'
    view.search.value='no matching case';view._filter_changed()
    assert view.clear_filters.visible and view.match_count==0 and view.draft_actions.visible
    view.clear_filters.on_click(None)
    assert not view.clear_filters.visible and view.match_count==378
    assert view.selected_case==key and view.case_converter.source==draft and repo.data.to_dict()==before


def test_restore_uses_the_selected_personal_variant_and_never_writes_to_storage():
    _,repo,_,view=open_library();key=view.selected_case
    sc=view.cases[key].starter
    view.state.save_case_algorithm(key,'Preferred',sc)
    alt=view.state.save_case_algorithm(key,'Alternative',sc+" F F'")
    view.select_case(key,algorithm_id=alt)
    before=deepcopy(repo.data.to_dict())
    with patch.object(repo,'save') as save:
        view.name_field.value='Renamed';view.name_field.on_change(None)
        assert view.draft_actions.visible
        view.case_converter.load('F R',notify=True)
        assert view.error.value
        view.restore_draft.on_click(None)
        assert view.selected_algorithm==alt and view.name_field.value=='Alternative'
        assert view.case_converter.source==sc+" F F'" and view.viewer.original_algorithm.source==sc+" F F'"
        assert not view.draft_actions.visible and not view.error.value
        assert repo.data.to_dict()==before
        save.assert_not_called()


def test_practice_shortcut_opens_the_same_trainer_and_keeps_its_filters():
    page,repo,_,view=open_library()
    before=deepcopy(repo.data.to_dict());view._set_mode('trainer')
    trainer=view.trainer;trainer.first_target.value='UBL';trainer._filter_changed()
    hub=click_nav(page,'Practice')
    next(b for b in walk(hub) if isinstance(b,ft.TextButton) and b.content=='Open corner trainer').on_click(None)
    assert page.root.controls[0].content is view and view.mode=='trainer'
    assert view.trainer is trainer and trainer.first_target.value=='UBL'
    assert repo.data.to_dict()==before
