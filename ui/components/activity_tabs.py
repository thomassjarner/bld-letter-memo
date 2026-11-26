"""Local activity navigation. The training keyboard only wraps the training body."""
from core.messages import message
from ui.language import present, tr
import flet as ft


class ActivityHeader:
    def __init__(self, title, back, actions, train_label, callback):
        self.title = ft.Text(present(title), size=23, weight=ft.FontWeight.W_600, expand=True,
                             max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
        self.back = ft.IconButton(ft.Icons.ARROW_BACK, tooltip=tr('Back to Practice'), icon_size=19, width=34, on_click=back)
        self.actions = ft.Container(actions)
        heading = ft.Row([self.back,
                          self.title, self.actions], height=44, spacing=6)
        self.picker = ft.SegmentedButton(
            segments=[ft.Segment(value="train", label=present(train_label)),
                      ft.Segment(value="stats", label=tr('Statistics'), icon=ft.Icons.SHOW_CHART)],
            selected=["train"], show_selected_icon=False, height=36,
            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=10),
                                 text_style=ft.TextStyle(size=13)),
            on_change=lambda e: callback(e.control.selected[0]))
        self.tabs = ft.Container(self.picker, left=0, top=4)
        self.view = ft.Stack([ft.Container(heading, left=0, right=0, top=0), self.tabs], height=44)

    def resize(self, width):
        wide = width >= 660
        self.view.width, self.view.height = width, 44 if wide else 86
        self.title.size = 23 if wide else 18
        self.tabs.left = 258 if wide else 0
        self.tabs.top = 4 if wide else 46

    def select(self, tab):
        self.picker.selected = [tab]
        self.actions.visible = tab == "train"
        self.back.tooltip = present(message('Back to Practice') if tab == 'train' else message('Back to {0}', self.title.value))
