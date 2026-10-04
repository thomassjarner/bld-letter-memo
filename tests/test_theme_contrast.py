"""Readable text in both themes, including previously inherited roles."""
import pytest
from ui.design import build_theme, TEXT_ROLES


def luminance(color):
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(a, b):
    low, high = sorted((luminance(a), luminance(b)))
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize('dark', [False, True])
def test_text_roles_and_status_colors_are_readable(dark):
    theme = build_theme(dark)
    scheme = theme.color_scheme
    surfaces = [scheme.surface, scheme.surface_container_lowest, scheme.surface_container_low]
    for role in TEXT_ROLES:
        color = getattr(theme.text_theme, role).color
        assert color, f'{role} must not inherit an unspecified foreground'
        for surface in surfaces:
            assert contrast(color, surface) >= 4.5, (dark, role, surface)
    for color in [scheme.on_surface_variant, scheme.primary, scheme.error, scheme.tertiary]:
        for surface in surfaces:
            assert contrast(color, surface) >= 4.5, (dark, color, surface)
    assert contrast(scheme.on_primary_container, scheme.primary_container) >= 4.5


def test_text_colors_change_between_modes():
    light, dark = build_theme(), build_theme(True)
    for role in TEXT_ROLES:
        assert getattr(light.text_theme, role).color != getattr(dark.text_theme, role).color
