"""Shared presentation tokens. No training or persistence logic lives here."""
import flet as ft
from data.color_themes import DEFAULT_LIGHT_THEME, light_theme as get_light_theme
from ui.feature_icons import feature_icon

PAGE_TITLE = 24
SECTION_TITLE = 16
BODY_TEXT = 13
SECONDARY_TEXT = 12
ICON_SIZE = 18
ACTION_HEIGHT = 36

TEXT_ROLES = (
    "body_large", "body_medium", "body_small",
    "display_large", "display_medium", "display_small",
    "headline_large", "headline_medium", "headline_small",
    "label_large", "label_medium", "label_small",
    "title_large", "title_medium", "title_small",
)


def build_theme(dark=False, light_theme=DEFAULT_LIGHT_THEME):
    overrides = {
        "body_medium": {"size": 13}, "body_small": {"size": 12},
        "title_medium": {"size": 16, "weight": ft.FontWeight.W_600},
    }
    colors = dict(
        primary="#6DD8C3", on_primary="#00382F",
        primary_container="#173F38", on_primary_container="#B7F1E2",
        secondary="#A6C9C0", secondary_container="#273B36", on_secondary_container="#DFEDE7",
        surface="#111917", on_surface="#F0F4F3", on_surface_variant="#BACBC6",
        surface_container_lowest="#0C1311", surface_container_low="#17201C",
        surface_container="#1C2822", surface_container_high="#24322B", surface_container_highest="#2C3B32",
        outline="#72867A", outline_variant="#35473D", error="#FFB4AB", tertiary="#FFD08A",
    ) if dark else dict(get_light_theme(light_theme).colors)
    button = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=8),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        icon_size=ICON_SIZE,
        text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
    )
    return ft.Theme(
        color_scheme_seed=colors["primary"], color_scheme=ft.ColorScheme(**colors),
        visual_density=ft.VisualDensity.COMPACT,
        # Explicit foregrounds prevent Flet defaults from leaving dark text on
        # dark surfaces. Cover every Material role, including form/dialog labels.
        text_theme=ft.TextTheme(**{
            role: ft.TextStyle(color=colors["on_surface"], **overrides.get(role, {}))
            for role in TEXT_ROLES
        }),
        button_theme=ft.ButtonTheme(style=button),
        outlined_button_theme=ft.OutlinedButtonTheme(style=button),
        text_button_theme=ft.TextButtonTheme(style=button),
        filled_button_theme=ft.FilledButtonTheme(style=button),
        icon_button_theme=ft.IconButtonTheme(style=ft.ButtonStyle(
            icon_size=ICON_SIZE, padding=6, shape=ft.RoundedRectangleBorder(radius=8))),
        scrollbar_theme=ft.ScrollbarTheme(thickness=5, radius=4),
    )


def eyebrow(text):
    return ft.Text(text.upper(), size=11, weight=ft.FontWeight.W_600,
                   color=ft.Colors.PRIMARY, style=ft.TextStyle(letter_spacing=.7))


def page_heading(title, description, label=None):
    return ft.Container(
        ft.Column([
            *([eyebrow(label)] if label else []),
            ft.Text(title, size=PAGE_TITLE, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
            ft.Text(description, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=4),
        padding=ft.Padding.only(bottom=8),
    )


def panel(content, padding=16, **kwargs):
    return ft.Container(
        content=content, padding=padding, border_radius=10,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), **kwargs,
    )


def activity_card(title, description, icon, action, on_click=None, number=None, enabled=True, *, feature=None):
    """Keyboard-accessible destination button; cards never mount tool controls."""
    return panel(ft.Column([
        ft.Row([
            ft.Container(feature_icon(feature, size=22, muted=not enabled) if feature else
                         ft.Icon(icon, size=20, color=ft.Colors.PRIMARY if enabled else ft.Colors.ON_SURFACE_VARIANT),
                         padding=8, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW if feature and enabled else
                         ft.Colors.PRIMARY_CONTAINER if enabled else ft.Colors.SURFACE_CONTAINER_HIGH,
                         border_radius=8),
            ft.Column([
                ft.Text(title, size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(number or ("Ready" if enabled else "Planned"), size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=2, expand=True),
        ], spacing=10, height=52),
        ft.Text(description, size=BODY_TEXT, color=ft.Colors.ON_SURFACE_VARIANT,
                height=52, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS, tooltip=description),
        ft.TextButton(action, icon=ft.Icons.ARROW_FORWARD,
                      height=ACTION_HEIGHT, disabled=not enabled, on_click=on_click),
    ], spacing=8, tight=True), col={"xs": 12, "md": 6}, padding=14)


def section_title(title, icon=None):
    return ft.Row([
        *([ft.Icon(icon, size=ICON_SIZE, color=ft.Colors.PRIMARY)] if icon else []),
        ft.Text(title, size=SECTION_TITLE, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
    ], spacing=8, height=24)


def action_button(label, *, primary=False, icon=None, on_click=None, **kwargs):
    cls = ft.FilledButton if primary else ft.OutlinedButton
    return cls(label, icon=icon, height=ACTION_HEIGHT, on_click=on_click, **kwargs)


def icon_action(icon, tooltip, on_click, *, size=36, **kwargs):
    return ft.IconButton(icon, tooltip=tooltip, on_click=on_click, icon_size=ICON_SIZE,
                         width=size, height=size, padding=6, **kwargs)
