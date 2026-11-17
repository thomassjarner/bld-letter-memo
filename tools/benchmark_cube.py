"""Time preparing and encoding camera/turn frames. Does not measure display FPS.

Run with the project's requirements installed: python tools/benchmark_cube.py
Use the same device and Python runtime when comparing two revisions.
"""
import json
import math
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

import flet as ft
import msgpack
from flet.controls.base_control import BaseControl
from flet.controls.object_patch import ObjectPatch
from flet.messaging.protocol import configure_encode_object_for_msgpack

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui.components.algorithm_cube import AlgorithmCube


def measure():
    cube = AlgorithmCube()
    cube.load("[R U R', D]")
    cube.set_viewport(600, 330)
    canvas = cube.canvas
    encode = configure_encode_object_for_msgpack(ft.Control)
    msgpack.packb(canvas, default=encode)
    reports = {}
    for kind in ('drag', 'turn'):
        samples, sizes, new_controls = [], [], []
        for i in range(78):
            if kind == 'drag':
                cube.yaw, cube.pitch = -.62 + i * .045, .45 + math.sin(i / 11) * .24
                cube._moving = None
            else:
                cube.yaw, cube.pitch = -.62, .45
                cube._moving = ('R', 'U2', 'Fw', 'M', 'x', ("D'", 'U'))[(i // 13) % 6]
                cube._fraction = (i % 13 + .5) / 13
            start = perf_counter()
            cube._redraw(update=False)
            patch, added, _ = ObjectPatch.from_diff(canvas, canvas, control_cls=BaseControl)
            wire = msgpack.packb(patch.to_message(), default=encode)
            elapsed = (perf_counter() - start) * 1000
            if i >= 4:  # warm up the renderer and serializer
                samples.append(elapsed)
                sizes.append(len(wire))
                new_controls.append(len(added))
        reports[kind] = dict(median_ms=round(median(samples), 2),
                             p95_ms=round(sorted(samples)[int(len(samples) * .95)], 2),
                             median_patch_bytes=median(sizes), median_new_controls=median(new_controls))
    return reports


if __name__ == '__main__':
    print(json.dumps(measure(), indent=2))
