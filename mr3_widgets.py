"""ConneX-style Tk controls. Values change only on user input, never while drawing."""
import tkinter as tk
from tkinter import ttk
from mr3_fonts import FONT
from mr3_icons import icon_image,BUTTON_ICONS
from mr3_dpi import dp

BG = '#000000'
CARD = '#232323'
FG = '#f5f5f5'
MUTED = '#929292'
ACCENT = '#dfbf7c'
LINE = '#393939'


def text(parent, value='', size=11, color=FG, **kwargs):
    kwargs.setdefault('anchor','w')
    return tk.Label(parent, text=value, bg=parent.cget('bg'), fg=color,
                    font=(FONT,size), **kwargs)


class AppButton(tk.Button):
    def __init__(self,parent,title,command,primary=False,icon=None,flat=False,**kwargs):
        self.icon_name=icon or BUTTON_ICONS.get(title)
        self.icon_cache={}
        background=parent.cget('bg') if flat else ACCENT if primary else '#292929'
        super().__init__(parent,text=('  ' if self.icon_name and title else '')+title,command=command,
                         font=(FONT,11),bg=background,fg=BG if primary else FG,
                         activebackground='#edcf91' if primary else '#383838',
                         activeforeground=BG if primary else FG,disabledforeground='#777777',
                         relief='flat',bd=0,highlightthickness=1,highlightbackground=background,
                         highlightcolor=ACCENT,padx=dp(14),pady=dp(9),cursor='hand2',compound='left',**kwargs)
        self.refresh_icon()

    def configure(self,cnf=None,**kwargs):
        result=super().configure(cnf,**kwargs)
        if kwargs and ('bg' in kwargs or 'background' in kwargs):
            super().configure(highlightbackground=self.cget('bg'))
        self.refresh_icon()
        return result

    config=configure

    def refresh_icon(self):
        if not self.icon_name: return
        color=self.cget('disabledforeground') if self.cget('state')=='disabled' else self.cget('fg')
        if color not in self.icon_cache: self.icon_cache[color]=icon_image(self,self.icon_name,color,dp(18))
        super().configure(image=self.icon_cache[color])


def button(parent,title,command,primary=False,**kwargs):
    return AppButton(parent,title,command,primary,**kwargs)


class BoundCanvas(tk.Canvas):
    def __init__(self,parent,variable,**kwargs):
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,bd=0,
                         takefocus=True,**kwargs)
        self.variable=variable
        self._trace=variable.trace_add('write',lambda *_:self.redraw())
        self.bind('<Configure>',lambda _:self.redraw())
        self.bind('<FocusIn>',lambda _:self.redraw())
        self.bind('<FocusOut>',lambda _:self.redraw())

    def destroy(self):
        self.variable.trace_remove('write',self._trace)
        super().destroy()

    def configure(self,cnf=None,**kwargs):
        result=super().configure(cnf,**kwargs)
        if hasattr(self,'variable'): self.redraw()
        return result

    config=configure

    def enabled(self):
        return self.cget('state')!='disabled'

    def focus_ring(self):
        if self.focus_get()==self and self.enabled():
            self.create_rectangle(1,1,self.winfo_width()-2,self.winfo_height()-2,outline=ACCENT)


class Toggle(BoundCanvas):
    def __init__(self,parent,variable,command=None):
        super().__init__(parent,variable,width=dp(52),height=dp(30),cursor='hand2')
        self.command=command
        self.images={}
        self.bind('<Button-1>',self.toggle)
        self.bind('<space>',self.toggle)
        self.bind('<Return>',self.toggle)

    def toggle(self,event=None):
        if self.enabled():
            self.focus_set()
            self.variable.set(not self.variable.get())
            if self.command: self.command()
        return 'break'

    def redraw(self):
        self.delete('all')
        on=self.variable.get()
        color=(ACCENT if on else '#555555') if self.enabled() else '#3b3b3b'
        key=(on,self.enabled())
        if key not in self.images:
            from PIL import Image,ImageDraw,ImageTk
            img=Image.new('RGBA',(208,120))
            draw=ImageDraw.Draw(img)
            draw.rounded_rectangle((8,8,200,112),radius=52,fill=color)
            x=37 if on else 15
            draw.ellipse(((x-11)*4,16,(x+11)*4,104),fill=FG if self.enabled() else '#777777')
            self.images[key]=ImageTk.PhotoImage(img.resize(dp((52,30)),Image.Resampling.LANCZOS),master=self)
        self.create_image(dp(26),dp(15),image=self.images[key])
        self.focus_ring()


class Slider(BoundCanvas):
    def __init__(self,parent,variable,values,vertical=False,labels=None,command=None,
                 width=180,height=40):
        super().__init__(parent,variable,width=dp(width),height=dp(height),cursor='hand2')
        self.values=list(values)
        self.vertical=vertical
        self.labels=labels
        self.command=command
        self.dragging=False
        self.knobs={}
        self.bind('<Button-1>',self.press)
        self.bind('<B1-Motion>',self.move)
        self.bind('<ButtonRelease-1>',self.release)
        self.bind('<KeyPress>',self.key)

    def index(self):
        try:
            value=float(self.variable.get())
            return min(range(len(self.values)),key=lambda i:abs(self.values[i]-value))
        except (ValueError,tk.TclError):
            return None

    def bounds(self):
        if self.vertical: return dp(16),max(dp(17),self.winfo_height()-dp(16))
        return dp(16),max(dp(17),self.winfo_width()-dp(16))

    def press(self,event):
        if not self.enabled(): return
        self.focus_set()
        self.dragging=True
        self.move(event)

    def move(self,event):
        if not self.enabled() or not self.dragging: return
        lo,hi=self.bounds()
        f=((hi-event.y) if self.vertical else (event.x-lo))/(hi-lo)
        index=round(max(0,min(1,f))*(len(self.values)-1))
        self.variable.set(self.values[index])

    def release(self,event):
        if not self.dragging: return
        self.dragging=False
        if self.enabled() and self.command: self.command()

    def key(self,event):
        if not self.enabled(): return
        index=self.index()
        if index is None: return
        if event.keysym in ('Left','Down'): index-=1
        elif event.keysym in ('Right','Up'): index+=1
        elif event.keysym=='Home': index=0
        elif event.keysym=='End': index=len(self.values)-1
        else: return
        self.variable.set(self.values[max(0,min(len(self.values)-1,index))])
        if self.command: self.command()
        return 'break'

    def redraw(self):
        # variable traces may fire after base init but before the slider is configured.
        if not hasattr(self,'values'): return
        self.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        lo,hi=self.bounds()
        index=self.index()
        active=self.enabled()
        track='#575757' if active else '#363636'
        if self.vertical:
            x=w/2
            self.create_line(x,lo,x,hi,fill=track,width=dp(3))
            for step in range(7):
                y=lo+(hi-lo)*step/6
                self.create_line(x-dp(9),y,x-dp(5),y,fill='#646464',width=dp(1))
            if index is not None:
                y=hi-(hi-lo)*index/(len(self.values)-1)
                self.create_line(x,y,x,hi,fill=FG if active else track,width=dp(3))
        else:
            x=None
            y=h-dp(18) if self.labels else h/2
            self.create_line(lo,y,hi,y,fill=track,width=dp(3 if self.labels else 6))
            if self.labels:
                for i,label in enumerate(self.labels):
                    tick=lo+(hi-lo)*i/(len(self.values)-1)
                    self.create_line(tick,y-dp(5),tick,y+dp(5),fill=track,width=dp(2))
                    self.create_text(tick,dp(12),text=label,fill=FG if i==index and active else MUTED,
                                     font=(FONT,10))
            if index is not None:
                x=lo+(hi-lo)*index/(len(self.values)-1)
                if not self.labels: self.create_line(lo,y,x,y,fill=ACCENT if active else track,width=dp(6))
        if index is not None:
            if active not in self.knobs:
                from PIL import Image,ImageDraw,ImageTk
                img=Image.new('RGBA',(80,80))
                draw=ImageDraw.Draw(img)
                draw.ellipse((4,4,76,76),fill=FG if active else '#707070')
                draw.ellipse((28,28,52,52),fill=BG)
                self.knobs[active]=ImageTk.PhotoImage(img.resize(dp((20,20)),Image.Resampling.LANCZOS),master=self)
            self.create_image(x,y,image=self.knobs[active])
        self.focus_ring()


class VolumeBar(Slider):
    """ConneX volume strip: full-height fill, bottom ticks and an inset value."""
    def __init__(self,parent,variable,display_variable,command=None):
        self.display_variable=display_variable
        super().__init__(parent,variable,range(31),height=60,command=command)
        self.display_trace=display_variable.trace_add('write',lambda *_:self.redraw())

    def bounds(self):
        return 0,max(1,self.winfo_width()-1)

    def redraw(self):
        if not hasattr(self,'values'): return
        from pathlib import Path
        from PIL import Image,ImageDraw,ImageFont,ImageTk
        self.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        index=self.index()
        known=not self.display_variable.get().startswith('—') and index is not None
        active=self.enabled()
        edge=(w-1)*index/30 if known else 0
        self.create_rectangle(0,0,w,h,fill='#202020',outline='')
        if edge:
            self.create_rectangle(0,0,edge,h,fill=ACCENT if active else '#71654b',outline='')
        for step in range(1,30):
            x=(w-1)*step/30
            self.create_line(x,h-dp(9 if step%5==0 else 6),x,h,
                             fill='#edcf92' if x<=edge and active else '#494949',width=1)
        label=f'현재 볼륨: {self.values[index]}' if known else '현재 볼륨: —'
        if not hasattr(self,'value_font'):
            self.value_font=ImageFont.truetype(str(Path(__file__).resolve().parent/'assets'/'fonts'/'Pretendard-Regular.ttf'),dp(15))
        # The label stays centred. Clip two text colours at the exact fill edge,
        # including when that edge crosses a letter, without moving the text.
        box=self.value_font.getbbox(label,anchor='lt')
        tw,th=box[2]-box[0],box[3]-box[1]
        mask=Image.new('L',(tw,th))
        ImageDraw.Draw(mask).text((-box[0],0),label,font=self.value_font,fill=255,anchor='lt')
        label_image=Image.new('RGBA',(tw,th),FG if active else MUTED)
        split=max(0,min(tw,round(edge-(w-tw)/2)))
        if split:
            ImageDraw.Draw(label_image).rectangle((0,0,split-1,th),fill=BG if active else '#ededed')
        label_image.putalpha(mask)
        self.value_image=ImageTk.PhotoImage(label_image,master=self)
        self.create_image(w/2,h/2,image=self.value_image,tags='volume-label')
        self.focus_ring()

    def destroy(self):
        self.display_variable.trace_remove('write',self.display_trace)
        super().destroy()


class Segments(tk.Frame):
    def __init__(self,parent,variable,values):
        super().__init__(parent,bg=parent.cget('bg'))
        self.variable=variable
        self.values=values
        self.enabled=True
        self.items=[]
        for value in values:
            item=button(self,value,lambda v=value:variable.set(v))
            item.pack(side='left',fill='x',expand=True,padx=dp((0,3)))
            self.items.append(item)
        self.trace=variable.trace_add('write',lambda *_:self.redraw())
        self.redraw()

    def configure(self,cnf=None,**kwargs):
        state=kwargs.pop('state',None)
        if state is not None:
            self.enabled=state!='disabled'
            self.redraw()
        return super().configure(cnf,**kwargs)

    def redraw(self):
        for value,item in zip(self.values,self.items):
            selected=self.variable.get()==value
            item.configure(bg=ACCENT if selected else '#303030',fg=BG if selected else FG,
                           activebackground=ACCENT if selected else '#414141',
                           activeforeground=BG if selected else FG,
                           state='normal' if self.enabled else 'disabled')

    def destroy(self):
        self.variable.trace_remove('write',self.trace)
        super().destroy()


class CircleButton(tk.Canvas):
    def __init__(self,parent,title,command,filled=False):
        super().__init__(parent,width=dp(32),height=dp(32),bg=parent.cget('bg'),
                         highlightthickness=0,bd=0,takefocus=True,cursor='hand2')
        self.title=title
        self.command=command
        self.filled=filled
        self.bind('<Button-1>',self.invoke)
        self.bind('<space>',self.invoke)
        self.bind('<Return>',self.invoke)
        self.bind('<FocusIn>',lambda _:self.redraw())
        self.bind('<FocusOut>',lambda _:self.redraw())
        self.redraw()

    def configure(self,cnf=None,**kwargs):
        result=super().configure(cnf,**kwargs)
        if hasattr(self,'title'): self.redraw()
        return result

    def invoke(self,event=None):
        if self.cget('state')!='disabled':
            self.focus_set()
            self.command()
        return 'break'

    def redraw(self):
        self.delete('all')
        color=FG if self.cget('state')!='disabled' else '#666666'
        self.create_oval(*dp((4,4,28,28)),outline=color,width=dp(1),fill=color if self.filled else '')
        self.create_text(dp(16),dp(15),text=self.title,fill=BG if self.filled else color,font=(FONT,12))
        if self.focus_get()==self: self.create_rectangle(*dp((1,1,31,31)),outline=ACCENT)


class MenuRow(tk.Canvas):
    """Whole-row target with a leading line icon and a chevron or selection radio."""
    def __init__(self,parent,title,subtitle,icon,command,variable=None,radio=None,value=None):
        super().__init__(parent,bg=BG,height=dp(62),highlightthickness=0,bd=0,takefocus=True,cursor='hand2')
        self.title,self.subtitle,self.command=title,subtitle,command
        self.variable,self.radio,self.value=variable,radio,value
        self.hover=False
        self.images={'icon':icon_image(self,icon,FG,dp(23)),'chevron':icon_image(self,'chevron',MUTED,dp(16))}
        self.traces=[]
        for var in (variable,radio):
            if var is not None: self.traces.append((var,var.trace_add('write',lambda *_:self.redraw())))
        self.bind('<Configure>',lambda _:self.redraw())
        self.bind('<Enter>',lambda _:self.set_hover(True))
        self.bind('<Leave>',lambda _:self.set_hover(False))
        self.bind('<FocusIn>',lambda _:self.redraw())
        self.bind('<FocusOut>',lambda _:self.redraw())
        self.bind('<Button-1>',self.invoke)
        self.bind('<Return>',self.invoke)
        self.bind('<space>',self.invoke)

    def configure(self,cnf=None,**kwargs):
        result=super().configure(cnf,**kwargs)
        if hasattr(self,'title'): self.redraw()
        return result

    def set_hover(self,value):
        self.hover=value
        self.redraw()

    def invoke(self,event=None):
        if self.cget('state')!='disabled':
            self.focus_set()
            self.command()
        return 'break'

    def redraw(self):
        self.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        selected=self.radio is not None and self.radio.get()==self.value
        self.configure_bg='#333333' if selected else '#1e1e1e' if self.radio is not None else BG
        super().configure(bg='#303030' if self.hover else self.configure_bg)
        sub=self.variable.get() if self.variable is not None else self.subtitle
        self.create_image(dp(28),h/2,image=self.images['icon'])
        self.create_text(dp(58),h/2-dp(10) if sub else h/2,text=self.title,anchor='w',fill=FG,font=(FONT,12))
        if sub:
            self.create_text(dp(58),h/2+dp(13),text=sub,anchor='w',fill=ACCENT if self.variable is not None else MUTED,
                             font=(FONT,10),width=max(1,w-dp(120)))
        if self.radio is not None:
            self.create_oval(w-dp(38),h/2-dp(9),w-dp(20),h/2+dp(9),outline=ACCENT if selected else '#777777',width=dp(1.5))
            if selected: self.create_oval(w-dp(34),h/2-dp(5),w-dp(24),h/2+dp(5),fill=ACCENT,outline='')
        else: self.create_image(w-dp(28),h/2,image=self.images['chevron'])
        self.create_line(0,h-1,w,h-1,fill='#292929')
        if self.focus_get()==self: self.create_rectangle(1,1,w-2,h-2,outline=ACCENT)

    def destroy(self):
        for var,trace in self.traces: var.trace_remove('write',trace)
        super().destroy()


class ModeChoices(tk.Frame):
    def __init__(self,parent,variable,values):
        super().__init__(parent,bg=parent.cget('bg'))
        self.rows=[]
        for title in values:
            row=MenuRow(self,title,'',BUTTON_ICONS[title],lambda v=title:variable.set(v),radio=variable,value=title)
            row.pack(fill='x',pady=dp(3))
            self.rows.append(row)

    def configure(self,cnf=None,**kwargs):
        state=kwargs.pop('state',None)
        if state is not None:
            for row in self.rows: row.configure(state=state)
        return super().configure(cnf,**kwargs)


class ScrollPage(tk.Frame):
    def __init__(self,parent):
        super().__init__(parent,bg=BG)
        self.canvas=tk.Canvas(self,bg=BG,bd=0,highlightthickness=0)
        self.scrollbar=ttk.Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.scrollbar.pack(side='right',fill='y')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side='left',fill='both',expand=True)
        self.content=tk.Frame(self.canvas,bg=BG)
        self.item=self.canvas.create_window(0,0,window=self.content,anchor='nw')
        self.content.bind('<Configure>',lambda _:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.item,width=e.width))

    def wheel(self,event):
        if self.content.winfo_reqheight()>self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(event.delta/120),'units')


class Pages:
    def __init__(self,parent):
        self.body=tk.Frame(parent,bg=BG)
        self.body.pack(fill='both',expand=True)
        self.body.rowconfigure(0,weight=1)
        self.body.columnconfigure(0,weight=1)
        self.pages=[]
        self.titles=[]
        self.parents=[]
        self.on_change=None
        self.current=0

    def add(self,title,parent=0):
        page=ScrollPage(self.body)
        page.grid(row=0,column=0,sticky='nsew')
        self.pages.append(page)
        self.titles.append(title)
        self.parents.append(parent)
        page.content.configure(padx=dp(24),pady=dp(20))
        return page.content

    def select(self,index):
        self.current=index
        for i,page in enumerate(self.pages):
            if i!=index: page.grid_remove()
        self.pages[index].grid()
        self.pages[index].tkraise()
        self.body.focus_set()
        if self.on_change: self.on_change(index)

    def back(self,event=None):
        self.select(self.parents[self.current])
        return 'break'

    def wheel(self,event):
        self.pages[self.current].wheel(event)

    def reveal(self,event):
        page=self.pages[self.current]
        widget=event.widget
        parent=widget
        while parent is not None and parent is not page.content:
            parent=getattr(parent,'master',None)
        if parent is None: return
        top=widget.winfo_rooty()-page.canvas.winfo_rooty()
        bottom=top+widget.winfo_height()
        height=page.canvas.winfo_height()
        offset=top-dp(8) if top<0 else bottom-height+dp(8) if bottom>height else 0
        if offset:
            total=max(1,page.content.winfo_height())
            page.canvas.yview_moveto(max(0,(page.canvas.canvasy(0)+offset)/total))
