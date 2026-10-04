"""Resolve presentation colors before sending controls to the Flet client.

Keep semantic roles with each UI object so repeated light/dark transitions are
reversible. User-entered rating colors and memo-cycle colors remain untouched.
No application data or persistent settings are traversed or changed.
"""
from dataclasses import fields, is_dataclass
from enum import Enum

import flet as ft
from ui.design import build_theme


def _defaults(control):
    if isinstance(control, (ft.Text, ft.TextField, ft.Dropdown)) and control.color is None:
        control.color = ft.Colors.ON_SURFACE
    for name in ('label_style', 'label_text_style', 'hint_style'):
        if hasattr(control, name):
            style = getattr(control, name)
            if style is None:
                setattr(control, name, ft.TextStyle(color=ft.Colors.ON_SURFACE_VARIANT if name == 'hint_style' else ft.Colors.ON_SURFACE))
            elif style.color is None:
                style.color = ft.Colors.ON_SURFACE
    if isinstance(control, ft.TabBar):
        if control.label_color is None:
            control.label_color = ft.Colors.PRIMARY
        if control.unselected_label_color is None:
            control.unselected_label_color = ft.Colors.ON_SURFACE_VARIANT
    if isinstance(control, (ft.TextButton, ft.OutlinedButton, ft.FilledButton, ft.Button, ft.IconButton)):
        if control.style is None:
            control.style = ft.ButtonStyle()
        if control.style.color is None:
            control.style.color = {
                ft.ControlState.DEFAULT: ft.Colors.ON_PRIMARY if isinstance(control, ft.FilledButton) else ft.Colors.PRIMARY,
                ft.ControlState.DISABLED: ft.Colors.ON_SURFACE_VARIANT,
            }
        if isinstance(control, ft.FilledButton) and control.style.bgcolor is None:
            control.style.bgcolor = {
                ft.ControlState.DEFAULT: ft.Colors.PRIMARY,
                ft.ControlState.DISABLED: ft.Colors.SURFACE_CONTAINER_HIGH,
            }


def apply_palette(root, dark):
    scheme = build_theme(dark).color_scheme
    palette = {f.name.replace('_', ''): getattr(scheme, f.name)
               for f in fields(scheme) if getattr(scheme, f.name) is not None}
    seen = set()

    def resolve(value):
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, str):
            return palette.get(value, value)
        if isinstance(value, dict):
            return {key: resolve(item) for key, item in value.items()}
        return value

    def visit(obj):
        if isinstance(obj, (list, tuple)):
            for child in obj:
                visit(child)
            return
        if not is_dataclass(obj) or id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, ft.Control):
            _defaults(obj)
        roles = getattr(obj, '_bld_color_roles', None)
        if roles is None:
            roles = {}
            object.__setattr__(obj, '_bld_color_roles', roles)
        for field in fields(obj):
            name = field.name
            if name.startswith('_') or name in ('data', 'parent', 'theme', 'dark_theme'):
                continue
            value = getattr(obj, name)
            if name == 'color' or name.endswith('color'):
                previous = roles.get(name)
                source = previous[0] if previous is not None and value == previous[1] else value
                resolved = resolve(source)
                roles[name] = (source, resolved)
                if resolved != value:
                    setattr(obj, name, resolved)
            else:
                visit(value)
    visit(root)


class ThemeAwarePage:
    def before_update(self):
        apply_palette(self, bool(self.data and self.data.data.dark_mode))


def show_themed_dialog(page, dialog, dark):
    apply_palette(dialog, dark)
    page.show_dialog(dialog)
