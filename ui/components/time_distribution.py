"""A compact frequency chart. Each time band and its count is always readable."""
from core.messages import message, compose
from ui.language import present, tr
import flet as ft

from core.training_statistics import format_time
from ui.design import panel


class TimeDistribution:
    def __init__(self):
        self.title = ft.Text(size=17,weight=ft.FontWeight.W_600)
        self.note = ft.Text(size=13,color=ft.Colors.ON_SURFACE_VARIANT)
        self.bands=[]
        for _ in range(6):
            label=ft.Text(size=14,expand=True)
            value=ft.Text(size=13,weight=ft.FontWeight.W_600)
            bar=ft.ProgressBar(value=0,height=6,border_radius=3,color=ft.Colors.PRIMARY,
                               bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH)
            row=ft.Column([ft.Row([label,value],spacing=6),bar],spacing=3,tight=True,
                          horizontal_alignment=ft.CrossAxisAlignment.STRETCH,visible=False)
            self.bands.append((row,label,value,bar))
        self.view=panel(ft.Column([self.title,self.note,*[r[0] for r in self.bands]],tight=True,
                             horizontal_alignment=ft.CrossAxisAlignment.STRETCH,spacing=9),padding=14)

    def set_profile(self,profile,*,timer,phase):
        n=len(profile.timed)
        self.title.value=present(message('Solve time distribution') if timer else message('{0} time distribution', message(phase.capitalize())))
        excluded=profile.total-n
        if timer and not n:
            self.note.value=tr('No successful times in this range. DNFs are excluded from the bars.')
        else:
            noun=message('successful solve') if timer else message('round')
            self.note.value=tr('{0} {1}{2}. Each bar is its share of these times.', n, noun, '' if n == 1 else message('s'))
            if timer and excluded:
                self.note.value+=tr(' {0} DNF{1} excluded.', excluded, '' if excluded == 1 else message('s'))
        bins=profile.bins()
        for i,(row,label,value,bar) in enumerate(self.bands):
            row.visible=i<len(bins)
            if row.visible:
                b=bins[i]
                label.value=(present(format_time(b.low) if b.low == b.high else compose('{0} – {1}', format_time(b.low), format_time(b.high))))
                bar.value=b.count / n
                share=("<0.1%" if 0<bar.value<.001 else ">99.9%" if .999<bar.value<1 else
                       compose('{0:.1f}', 100 * bar.value).removesuffix(".0")+"%")
                value.value=present(compose('{0} · {1}', b.count, share))
                row.tooltip=tr('{0}: {1} of {2} {3}', label.value, b.count, n, message('successful solves') if timer else message('rounds'))
