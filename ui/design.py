"""Shared presentation tokens. No training or persistence logic lives here."""
import flet as ft


TEXT_ROLES = (
    "body_large", "body_medium", "body_small",
    "display_large", "display_medium", "display_small",
    "headline_large", "headline_medium", "headline_small",
    "label_large", "label_medium", "label_small",
    "title_large", "title_medium", "title_small",
)


def build_theme(dark=False):
    overrides = {
        "body_medium": {"size": 13}, "body_small": {"size": 12},
        "title_medium": {"size": 16, "weight": ft.FontWeight.W_600},
    }
    colors = dict(
        primary="#6DD8C3" if dark else "#006B5B",
        on_primary="#00382F" if dark else "#FFFFFF",
        primary_container="#173F38" if dark else "#D7F0E8",
        on_primary_container="#B7F1E2" if dark else "#094B3E",
        secondary="#A6C9C0" if dark else "#48675E",
        secondary_container="#273B36" if dark else "#E5EEE9",
        on_secondary_container="#DFEDE7" if dark else "#223F35",
        surface="#111917" if dark else "#FAFCFA",
        on_surface="#F0F4F3" if dark else "#182B25",
        on_surface_variant="#BACBC6" if dark else "#52685E",
        surface_container_lowest="#0C1311" if dark else "#FFFFFF",
        surface_container_low="#17201C" if dark else "#F3F6F2",
        surface_container="#1C2822" if dark else "#EBF0EA",
        surface_container_high="#24322B" if dark else "#E4EBE3",
        surface_container_highest="#2C3B32" if dark else "#DBE5DA",
        outline="#72867A" if dark else "#7C8F82",
        outline_variant="#35473D" if dark else "#D7E1D5",
        error="#FFB4AB" if dark else "#BA1A1A",
        tertiary="#FFD08A" if dark else "#825000",
    )
    button = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=7),
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
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
        scrollbar_theme=ft.ScrollbarTheme(thickness=5, radius=4),
    )


def eyebrow(text):
    return ft.Text(text.upper(), size=10, weight=ft.FontWeight.BOLD,
                   color=ft.Colors.PRIMARY, style=ft.TextStyle(letter_spacing=1.4))


def page_heading(title, description, label=None):
    return ft.Container(
        ft.Column([
            *([eyebrow(label)] if label else []),
            ft.Text(title, size=25, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
            ft.Text(description, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=4),
        padding=ft.Padding.only(bottom=14),
    )


def panel(content, padding=16, **kwargs):
    return ft.Container(
        content=content, padding=padding, border_radius=10,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOWEST,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT), **kwargs,
    )


def activity_card(title, description, icon, action, on_click=None, number=None, enabled=True):
    """Keyboard-accessible destination button; cards never mount tool controls."""
    return panel(ft.Column([
        ft.Row([
            ft.Container(ft.Icon(icon, size=21, color=ft.Colors.PRIMARY),
                         padding=9, bgcolor=ft.Colors.PRIMARY_CONTAINER, border_radius=8),
            ft.Text(number or ("READY" if enabled else "PLANNED"), size=10,
                    color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Text(title, size=19, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
        ft.Text(description, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        ft.TextButton(action, icon=ft.Icons.ARROW_FORWARD,
                      disabled=not enabled, on_click=on_click),
    ], spacing=10), col={"xs": 12, "md": 6}, padding=18)
