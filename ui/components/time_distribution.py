"""A compact frequency chart. Each time band and its count is always readable."""
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
        self.title.value="Solve time distribution" if timer else f"{phase.capitalize()} time distribution"
        excluded=profile.total-n
        if timer and not n:
            self.note.value="No successful times in this range. DNFs are excluded from the bars."
        else:
            noun="successful solve" if timer else "round"
            self.note.value=f"{n} {noun}{'' if n==1 else 's'}. Each bar is its share of these times."
            if timer and excluded:
                self.note.value+=f" {excluded} DNF{'' if excluded==1 else 's'} excluded."
        bins=profile.bins()
        for i,(row,label,value,bar) in enumerate(self.bands):
            row.visible=i<len(bins)
            if row.visible:
                b=bins[i]
                label.value=(format_time(b.low) if b.low==b.high else f"{format_time(b.low)} – {format_time(b.high)}")
                bar.value=b.count/n
                share=("<0.1%" if 0<bar.value<.001 else ">99.9%" if .999<bar.value<1 else
                       f"{100*bar.value:.1f}".removesuffix(".0")+"%")
                value.value=f"{b.count} · {share}"
                row.tooltip=f"{label.value}: {b.count} of {n} "+("successful solves" if timer else "rounds")
