"""Client-side route fades; never insert a delay in keyboard or timing handlers."""
import flet as ft


def route_switcher(content, **layout):
    return ft.AnimatedSwitcher(content=content, duration=150, reverse_duration=95,
        transition=ft.AnimatedSwitcherTransition.FADE,
        switch_in_curve=ft.AnimationCurve.EASE_OUT, switch_out_curve=ft.AnimationCurve.EASE_IN,
        **layout)


def set_reduced_motion(switcher, reduced):
    switcher.duration = 0 if reduced else 150
    switcher.reverse_duration = 0 if reduced else 95
