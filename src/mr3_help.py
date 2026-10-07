"""Non-modal help bubbles drawn inside the main window, without a Toplevel."""
import tkinter as tk
from mr3_dpi import dp
from mr3_fonts import FONT


class HelpPopover:
    def __init__(self, root):
        self.root = root
        self.anchor = None
        self.color = '#303030'
        self.panel = tk.Frame(root, bg=self.color, highlightthickness=1,
                              highlightbackground='#666052')
        self.title = tk.Label(self.panel, bg=self.color, fg='#dfbf7c',
                              font=(FONT, 11, 'bold'), anchor='w', justify='left')
        self.title.pack(fill='x', padx=dp(18), pady=dp((14, 7)))
        self.body = tk.Label(self.panel, bg=self.color, fg='#f5f5f5',
                             font=(FONT, 11), anchor='w', justify='left')
        self.body.pack(fill='x', padx=dp(18), pady=dp((0, 16)))
        self.pointer = tk.Canvas(root, bg='#232323', bd=0, highlightthickness=0,
                                 width=dp(18), height=dp(10))
        self.tag = f'MR3Help_{id(self)}'
        root.bind_class(self.tag, '<Button-1>', self.outside_click)
        root.bind('<Escape>', self.escape, add='+')
        root.bind('<MouseWheel>', lambda _: self.hide(), add='+')
        root.bind('<Configure>', self.window_changed, add='+')
        root.bind('<Unmap>', self.window_changed, add='+')
        root.bind('<Destroy>', self.destroyed, add='+')

    def install(self, widget=None):
        """Dismiss before a control consumes its click; never swallow that click."""
        widget = widget or self.root
        if self.tag not in widget.bindtags():
            widget.bindtags((self.tag,) + widget.bindtags())
        for child in widget.winfo_children():
            self.install(child)

    def toggle(self, anchor, title, description):
        if self.anchor is anchor:
            self.hide()
            return
        self.hide()
        self.root.update_idletasks()
        self.title.configure(text=title)
        width = min(dp(370), self.root.winfo_width() - dp(24))
        self.title.configure(wraplength=max(1, width - dp(38)))
        self.body.configure(text=description, wraplength=max(1, width - dp(38)))
        self.panel.update_idletasks()
        height = self.panel.winfo_reqheight()
        ax = anchor.winfo_rootx() - self.root.winfo_rootx() + anchor.winfo_width() // 2
        ay = anchor.winfo_rooty() - self.root.winfo_rooty()
        x = max(dp(12), min(ax - width + dp(24), self.root.winfo_width() - width - dp(12)))
        below = ay + anchor.winfo_height() + dp(8)
        down = below + height <= self.root.winfo_height() - dp(12)
        y = below if down else max(dp(12), ay - dp(8) - height)
        self.pointer.configure(bg=anchor.cget('bg'))
        self.pointer.delete('all')
        coords = (0, 10, 9, 0, 18, 10) if down else (0, 0, 9, 10, 18, 0)
        self.pointer.create_polygon(*dp(coords), fill=self.color, outline='')
        self.panel.place(x=x, y=y, width=width, height=height)
        self.pointer.place(x=max(x+dp(10), min(ax-dp(9), x+width-dp(28))),
                           y=y-dp(9) if down else y+height-dp(1))
        self.panel.lift()
        tk.Misc.lift(self.pointer)
        self.anchor = anchor

    def hide(self):
        self.panel.place_forget()
        self.pointer.place_forget()
        self.anchor = None

    def escape(self, event=None):
        if self.anchor is not None:
            self.hide()
            return 'break'

    def outside_click(self, event):
        current = event.widget
        while current is not None:
            if current in (self.anchor, self.panel, self.pointer):
                return
            current = getattr(current, 'master', None)
        self.hide()

    def window_changed(self, event):
        if event.widget is self.root:
            self.hide()

    def destroyed(self, event):
        if event.widget is self.root:
            self.root.unbind_class(self.tag, '<Button-1>')
