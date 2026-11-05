"""Named light palettes shared by preferences and presentation; no Flet dependency."""
from dataclasses import dataclass
from typing import Mapping


DEFAULT_LIGHT_THEME = "classic_teal"


@dataclass(frozen=True)
class LightTheme:
    name: str
    description: str
    colors: Mapping[str, str]


LIGHT_THEMES = {
    "classic_teal": LightTheme("Classic Teal", "Fresh greens and a familiar teal accent.", dict(
        primary="#006B5B", on_primary="#FFFFFF",
        primary_container="#D7F0E8", on_primary_container="#094B3E",
        secondary="#48675E", secondary_container="#E5EEE9", on_secondary_container="#223F35",
        surface="#FAFCFA", on_surface="#182B25", on_surface_variant="#52685E",
        surface_container_lowest="#FFFFFF", surface_container_low="#F3F6F2",
        surface_container="#EBF0EA", surface_container_high="#E4EBE3", surface_container_highest="#DBE5DA",
        outline="#7C8F82", outline_variant="#D7E1D5", error="#BA1A1A", tertiary="#825000",
    )),
    "cobalt": LightTheme("Cobalt Blue", "Cool blue surfaces with a crisp cobalt accent.", dict(
        primary="#2453B3", on_primary="#FFFFFF",
        primary_container="#DCE7FF", on_primary_container="#163A7C",
        secondary="#4E6284", secondary_container="#E3EAF6", on_secondary_container="#2D4261",
        surface="#FAFBFF", on_surface="#1B2942", on_surface_variant="#475A76",
        surface_container_lowest="#FFFFFF", surface_container_low="#F0F4FC",
        surface_container="#E7EDF8", surface_container_high="#DCE5F5", surface_container_highest="#D3DFF2",
        outline="#7386A5", outline_variant="#CFD9EB", error="#BA1A1A", tertiary="#754000",
    )),
    "lavender": LightTheme("Lavender", "Soft lilac panels and a clear violet accent.", dict(
        primary="#6B43A6", on_primary="#FFFFFF",
        primary_container="#EADDF9", on_primary_container="#482477",
        secondary="#635174", secondary_container="#EDE4F4", on_secondary_container="#493751",
        surface="#FDFBFF", on_surface="#30233F", on_surface_variant="#63516E",
        surface_container_lowest="#FFFFFF", surface_container_low="#F5F0FA",
        surface_container="#EEE6F5", surface_container_high="#E7DCEF", surface_container_highest="#DFD2EB",
        outline="#92819F", outline_variant="#DFD2EB", error="#B11B1B", tertiary="#775000",
    )),
    "warm_sand": LightTheme("Warm Sand", "Warm ivory surfaces with a rich amber accent.", dict(
        primary="#874B1B", on_primary="#FFFFFF",
        primary_container="#F7DFC0", on_primary_container="#63370F",
        secondary="#695942", secondary_container="#EEE3D1", on_secondary_container="#4F412D",
        surface="#FFFDF8", on_surface="#382C1E", on_surface_variant="#665741",
        surface_container_lowest="#FFFEFB", surface_container_low="#F9F2E7",
        surface_container="#F1E8D7", surface_container_high="#EADFC9", surface_container_highest="#E2D4B9",
        outline="#96846B", outline_variant="#DDCFB6", error="#B11B1B", tertiary="#4C6251",
    )),
    "rose": LightTheme("Rose", "Pale rose surfaces with a deep berry accent.", dict(
        primary="#A23660", on_primary="#FFFFFF",
        primary_container="#F8DCE7", on_primary_container="#76203F",
        secondary="#755364", secondary_container="#F0E2EB", on_secondary_container="#533346",
        surface="#FFFAFC", on_surface="#3E2431", on_surface_variant="#70505F",
        surface_container_lowest="#FFFFFF", surface_container_low="#FAF0F4",
        surface_container="#F5E5EC", surface_container_high="#F0DBE5", surface_container_highest="#EBD0DD",
        outline="#AA8192", outline_variant="#E6CED9", error="#B11B1B", tertiary="#465A7A",
    )),
}


def normalize_light_theme(value) -> str:
    """Older backups and unrecognised choices keep the original appearance."""
    return value if isinstance(value, str) and value in LIGHT_THEMES else DEFAULT_LIGHT_THEME


def light_theme(value=DEFAULT_LIGHT_THEME) -> LightTheme:
    return LIGHT_THEMES[normalize_light_theme(value)]
