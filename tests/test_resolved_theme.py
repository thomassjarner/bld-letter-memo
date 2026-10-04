"""Check concrete control colors, not only the theme's configured palette."""
import flet as ft
from ui.theme_colors import apply_palette
from test_navigation import mount, click_nav, walk, no_client_mount
from test_theme_contrast import contrast


def toggle(page, dark):
    tooltip = 'Switch to dark mode' if dark else 'Switch to light mode'
    next(c for c in walk(page.root) if isinstance(c, ft.IconButton) and c.tooltip == tooltip).on_click(None)


def test_actual_screen_text_and_inputs_switch_both_directions():
    page, repo = mount()
    for dark in (True, False, True):
        toggle(page, dark)
        expected = '#F0F4F3' if dark else '#182B25'
        surface = '#17201C' if dark else '#FAFCFA'
        for label in ('Home', 'Letter Schemes', 'Letter Pairs', 'Scramble Memo', 'Practice', 'Timer', 'Settings'):
            view = click_nav(page, label)
            view.before_update()
            texts = [c for c in walk(view) if isinstance(c, ft.Text)]
            assert texts and any(c.color == expected for c in texts), label
            for text in texts:
                assert isinstance(text.color, str) and text.color.startswith('#'), (label, text.value, text.color)
                assert contrast(text.color, surface) >= 4.5, (label, text.value, text.color)
            for control in walk(view):
                if isinstance(control, (ft.TextField, ft.Dropdown)):
                    assert control.color == expected
        assert repo.data.dark_mode == dark


def test_rebuilt_children_and_semantic_status_changes_get_concrete_colors():
    page, _ = mount()
    toggle(page, True)
    timer = click_nav(page, 'Timer')
    timer.timer_text.color = ft.Colors.PRIMARY
    timer.before_update()
    assert timer.timer_text.color == '#6DD8C3'
    timer.timer_text.color = ft.Colors.ON_SURFACE
    timer.before_update()
    assert timer.timer_text.color == '#F0F4F3'
    settings = click_nav(page, 'Settings')
    settings.controls.append(ft.Text('Created after the theme switch'))
    settings.before_update()
    assert settings.controls[-1].color == '#F0F4F3'


def test_dialog_labels_buttons_and_user_colors():
    custom = ft.Container(bgcolor='#FF00FF')
    dialog = ft.AlertDialog(title=ft.Text('Confirm'), content=ft.Column([
        ft.TextField(label='Name'), ft.Checkbox(label='Enabled'), custom,
    ]), actions=[ft.FilledButton('Accept'), ft.TextButton('Cancel')])
    for dark, expected in ((True, '#F0F4F3'), (False, '#182B25'), (True, '#F0F4F3')):
        apply_palette(dialog, dark)
        assert dialog.title.color == expected
        assert dialog.content.controls[0].color == expected
        assert dialog.content.controls[1].label_style.color == expected
        assert custom.bgcolor == '#FF00FF'
        assert dialog.actions[0].style.color[ft.ControlState.DEFAULT] == ('#00382F' if dark else '#FFFFFF')


def test_filled_button_wire_style_uses_resolved_colors():
    button = ft.FilledButton('Save')
    apply_palette(button, True)
    button.before_update()
    assert button._internals['style'].color[ft.ControlState.DEFAULT] == '#00382F'
    assert button._internals['style'].bgcolor[ft.ControlState.DEFAULT] == '#6DD8C3'
