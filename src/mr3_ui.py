"""Desktop arrangement of the black, charcoal and gold ConneX control screens."""
from mr3_paths import RESOURCE_DIR
import tkinter as tk
from mr3_dpi import dp
from mr3_help import HelpPopover
from pathlib import Path
from PIL import Image,ImageTk
from mr3_widgets import BG,CARD,FG,MUTED,ACCENT,LINE,FONT,text,button,Toggle,Slider,VolumeBar,Segments,Pages,CircleButton,MenuRow,ModeChoices


def build_interface(app):
    root=app.root
    app.help_popover=HelpPopover(root)
    app.help_buttons={}
    outer=tk.Frame(root,bg=BG)
    outer.pack(fill='both',expand=True)

    def action(parent,title,callback,primary=False,connected=True,**pack):
        item=button(parent,title,callback,primary)
        item.pack(**pack)
        app.buttons.append((item,connected))
        return item

    def editor(widget,**pack):
        widget.pack(**pack)
        app.editors.append((widget,'normal'))
        return widget

    def line(parent,pady=0,padx=0):
        row=tk.Frame(parent,bg=parent.cget('bg'))
        row.pack(fill='x',pady=dp(pady),padx=dp(padx))
        return row

    def card(parent,title=None,help_text=None):
        box=tk.Frame(parent,bg=CARD)
        box.pack(fill='x',pady=dp((0,14)))
        if title:
            heading=line(box,padx=20,pady=6)
            text(heading,title,12).pack(side='left')
            if help_text:
                help_button=CircleButton(heading,'?',lambda:app.help_popover.toggle(help_button,title,help_text),filled=True)
                help_button.pack(side='right')
                app.help_buttons[title]=help_button
            tk.Frame(box,bg=BG,height=dp(1)).pack(fill='x')
        body=tk.Frame(box,bg=CARD,padx=dp(20),pady=dp(10))
        body.pack(fill='x')
        return body

    def entry(parent,var,width=25):
        return tk.Entry(parent,textvariable=var,width=width,bg='#191919',fg=FG,
                        insertbackground=FG,disabledbackground='#1c1c1c',disabledforeground=MUTED,
                        relief='flat',highlightthickness=1,highlightbackground='#4b4b4b',
                        highlightcolor=ACCENT,font=(FONT,11))

    def switch_row(parent,title,var,description='',command=None,device=False):
        row=line(parent,pady=9)
        copy=tk.Frame(row,bg=CARD)
        copy.pack(side='left',fill='x',expand=True)
        text(copy,title,11).pack(anchor='w')
        if description: text(copy,description,9,MUTED).pack(anchor='w',pady=dp((4,0)))
        toggle=Toggle(row,var,command)
        toggle.pack(side='right',padx=dp((16,0)))
        if device: app.editors.append((toggle,'normal'))
        return toggle

    app.home_name_var=tk.StringVar(value=app.config.get('device_name','EDIFIER MR3'))
    app.home_mode_var=tk.StringVar(value='연결 후 설정 확인')
    app.home_tuning_var=tk.StringVar(value='로우 컷오프 · 어쿠스틱 스페이스 · 데스크톱 컨트롤')
    app.page_title=tk.StringVar(value=app.home_name_var.get())
    header=line(outer,padx=24,pady=(15,6))
    header.columnconfigure(0,weight=1,uniform='side')
    header.columnconfigure(1,weight=2)
    header.columnconfigure(2,weight=1,uniform='side')
    left=tk.Frame(header,bg=BG); left.grid(row=0,column=0,sticky='w')
    right=tk.Frame(header,bg=BG); right.grid(row=0,column=2,sticky='e')
    app.back_button=button(left,'뒤로',lambda:app.book.back(),icon='back',flat=True)
    picker=button(left,'기기 선택',app.open_devices,flat=True)
    picker.pack(side='left')
    app.buttons.append((picker,False))
    text(header,'',18,textvariable=app.page_title,anchor='center').grid(row=0,column=1,sticky='ew')
    button(right,'',lambda:app.book.select(3),icon='settings',flat=True).pack(side='right')
    app.cancel_button=button(right,'취소',app.cancel_connection,flat=True)
    status=line(outer,padx=25,pady=(0,12))
    app.status_label=text(status,'',9,MUTED,textvariable=app.status,wraplength=dp(820),anchor='center')
    app.status_label.pack(fill='x')
    tk.Frame(outer,bg=LINE,height=dp(1)).pack(fill='x')

    # Persistent bottom bar, like the device volume controls in ConneX.
    bottom=tk.Frame(outer,bg=BG,padx=dp(25),pady=dp(12))
    bottom.pack(side='bottom',fill='x')
    text(bottom,'볼륨 조절',12,anchor='center').pack(fill='x')
    app.vol_slider=VolumeBar(bottom,app.volume,app.volume_text,
        command=lambda:app.submit(app.client.set_volume,round(app.volume.get())))
    app.vol_slider.pack(fill='x',pady=dp((12,0)))
    text(bottom,'',9,MUTED,textvariable=app.read_status).pack(anchor='w',pady=dp((4,0)))

    book=app.book=Pages(outer)
    home=book.add('EDIFIER MR3')
    sound=book.add('음향 효과')
    room=book.add('어쿠스틱 튜닝')
    device=book.add('내 기기')
    settings=book.add('앱 설정')
    custom=book.add('사용자 설정',parent=1)
    def change_page(index):
        app.help_popover.hide()
        app.page_title.set(app.home_name_var.get() if index==0 else book.titles[index])
        if index==0:
            app.back_button.pack_forget()
            picker.pack(side='left')
        else:
            picker.pack_forget()
            app.back_button.pack(side='left')
    book.on_change=change_page
    app.home_name_var.trace_add('write',lambda *_:change_page(book.current))
    root.bind('<MouseWheel>',book.wheel,add='+')
    root.bind('<FocusIn>',book.reveal,add='+')
    root.bind('<Alt-Left>',book.back,add='+')
    root.bind('<Escape>',book.back,add='+')

    picture=tk.Canvas(home,bg=BG,height=dp(254),highlightthickness=0,bd=0)
    picture.pack(fill='x',pady=dp((0,12)))
    with Image.open(RESOURCE_DIR/'assets'/'mr3-product.png') as product:
        app.product_image=ImageTk.PhotoImage(product.resize(dp((512,512)),Image.Resampling.LANCZOS),master=root)
    picture.create_image(0,dp(127),image=app.product_image,tags='product')
    picture.bind('<Configure>',lambda e:picture.coords('product',e.width/2,e.height/2))
    app.home_rows=[]
    for title,subtitle,icon,target,var in (
        ('음향 효과','','eq',1,app.home_mode_var),
        ('어쿠스틱 튜닝','','tune',2,app.home_tuning_var),
        ('내 기기','기기 이름 · 연결 안내음 · 연결 및 백업','speaker',3,None),
        ('앱 설정','자동 실행 · 트레이 · 볼륨 알림','settings',4,None)):
        row=MenuRow(home,title,subtitle,icon,lambda i=target:book.select(i),variable=var)
        row.pack(fill='x')
        app.home_rows.append(row)

    editor(ModeChoices(sound,app.mode,('모니터','음악','사용자 설정')),fill='x')
    row=line(sound,pady=(14,22))
    text(row,'선택한 음향 모드를 스피커에 적용합니다.',10,MUTED).pack(side='left')
    action(row,'적용',lambda:app.submit(app.client.set_mode,('모니터','음악','사용자 설정').index(app.mode.get())),primary=True,side='right')
    MenuRow(sound,'사용자 EQ','9개 대역의 게인과 기반 모드를 조절합니다.','eq',lambda:book.select(5)).pack(fill='x')
    MenuRow(sound,'어쿠스틱 튜닝','스피커 위치에 맞춰 저음을 보정합니다.','tune',lambda:book.select(2)).pack(fill='x')

    eq=card(custom,'사운드 효과',
            '9개 주파수 대역을 −3 ~ +3dB 범위에서 조절합니다.\n사용자 설정 모드에서 EQ 적용을 누르면 스피커에 저장됩니다.')
    row=line(eq)
    text(row,'게인',10).pack(side='left')
    text(row,'−3 ~ +3 dB',9,MUTED).pack(side='right')
    bands=line(eq,pady=(12,14))
    app.eq_value_labels=[]
    for var,hz in zip(app.gains,('62','125','250','500','1k','2k','4k','8k','16k')):
        col=tk.Frame(bands,bg=CARD)
        col.pack(side='left',fill='x',expand=True)
        editor(Slider(col,var,[i/2 for i in range(-6,7)],vertical=True,width=50,height=135),fill='x')
        text(col,hz+'Hz',9,MUTED,anchor='center').pack(fill='x',pady=dp((5,2)))
        label=text(col,'—',10,anchor='center')
        label.pack(fill='x')
        app.eq_value_labels.append(label)
        def update_gain(*_,v=var,l=label):
            l.configure(text=f'{v.get():g}dB' if app.state.get('eq') else '—')
        var.trace_add('write',update_gain)
    row=line(eq,pady=(0,12))
    text(row,'기반 모드',10).pack(side='left')
    editor(Segments(row,app.base,('모니터','음악')),side='right',fill='x',padx=dp((24,0)))
    row=line(eq,pady=(0,10))
    editor(entry(row,app.eq_name),side='left',fill='x',expand=True,ipady=dp(9))
    action(row,'이름 저장',lambda:app.submit(app.client.rename_eq,app.eq_name.get()),side='right',padx=dp((10,0)))
    row=line(eq)
    action(row,'불러오기',app.load_profile,connected=False,side='left')
    action(row,'파일 저장',app.save_profile,connected=False,side='left',padx=dp(8))
    action(row,'EQ 적용',app.apply_eq,primary=True,side='right')
    action(row,'0dB로 편집',lambda:[v.set(0) for v in app.gains],connected=False,side='right',padx=dp(8))

    cutoff=card(room,'로우 컷오프','설정한 주파수 아래의 저음을 줄입니다.\n슬로프의 절댓값이 클수록 더 급격히 줄어듭니다.')
    cutoff_label=text(cutoff,'주파수: —',12)
    cutoff_label.pack(anchor='w')
    app.cutoff.trace_add('write',lambda *_:cutoff_label.configure(text='주파수: '+(app.cutoff.get()+'Hz' if app.cutoff.get() else '—')))
    row=line(cutoff,pady=(4,8))
    def step_cutoff(delta):
        if app.cutoff.get(): app.cutoff.set(str(max(20,min(100,int(app.cutoff.get())+delta))))
    for title,delta,side in (('−',-5,'left'),('+',5,'right')):
        item=CircleButton(row,title,lambda d=delta:step_cutoff(d))
        item.pack(side=side)
        app.buttons.append((item,True))
    editor(Slider(row,app.cutoff,range(20,101,5),height=32),side='left',fill='x',expand=True,padx=dp(10))
    slope_label=text(cutoff,'슬로프: —',12)
    slope_label.pack(anchor='w')
    app.slope.trace_add('write',lambda *_:slope_label.configure(text='슬로프: '+(app.slope.get()+'dB/octave' if app.slope.get() else '—')))
    editor(Slider(cutoff,app.slope,[-6,-12,-18,-24],labels=['−6','−12','−18','−24'],height=52),fill='x',pady=dp((4,0)))
    space=card(room,'어쿠스틱 스페이스','벽이나 모서리 가까이 놓았을 때 과해지는 저음을 보정합니다.\n0dB에서 −4dB까지 조절할 수 있습니다.')
    editor(Slider(space,app.space,[0,-1,-2,-3,-4],labels=['0dB','−1dB','−2dB','−3dB','−4dB'],height=48),fill='x')
    desktop=card(room,'데스크톱 컨트롤','책상 표면의 반사로 생기는 음색 변화를 보정합니다.')
    row=line(desktop)
    desktop_label=text(row,'—',12)
    desktop_label.pack(side='left')
    app.desktop.trace_add('write',lambda *_:desktop_label.configure(text='켬' if app.desktop.get() else '끔'))
    editor(Toggle(row,app.desktop),side='right')
    row=line(room,pady=(0,8))
    text(row,'현재 음향 모드에 적용됩니다.',9,MUTED).pack(side='left')
    action(row,'튜닝 적용',app.apply_room,primary=True,side='right')

    identity=card(device,'EDIFIER MR3')
    row=line(identity,pady=(0,16))
    action(row,'기기 선택',app.open_devices,connected=False,side='left')
    action(row,'연결',app.connect,connected=False,side='left',padx=dp(8))
    action(row,'연결 해제',lambda:app.submit(app.client.disconnect),side='right')
    row=line(identity,pady=(0,14))
    text(row,'기기 이름',11).pack(side='left')
    editor(entry(row,app.device_name),side='left',fill='x',expand=True,padx=dp(20),ipady=dp(8))
    action(row,'저장',lambda:app.submit(app.client.rename,app.device_name.get()),side='right')
    app.info=text(identity,'펌웨어 —',10,MUTED)
    app.info.pack(anchor='w')
    tones=card(device,'안내음')
    switch_row(tones,'블루투스 연결 안내음',app.beep,device=True)
    action(tones,'안내음 적용',lambda:app.submit(app.client.set_beep,app.beep.get()),side='right')
    connection=card(device,'연결 및 백업')
    text(connection,'최초 연결 시 제어용 BLE 페어링을 자동으로 진행합니다.',9,MUTED).pack(anchor='w',pady=dp((0,12)))
    row=line(connection,pady=(0,14))
    text(row,'저장된 기기 주소',10).pack(side='left')
    entry(row,app.address).pack(side='left',fill='x',expand=True,padx=dp(16),ipady=dp(8))
    action(row,'새로 읽기',lambda:app.submit(app.client.refresh),side='right')
    row=line(connection)
    text(row,'설정을 적용하기 전에 원본을 자동으로 백업합니다.',9,MUTED).pack(side='left')
    action(row,'백업 복원',app.restore_backup,side='right')
    text(device,'펌웨어 업데이트와 공장 초기화는 ConneX 앱에서 이용하세요.',9,MUTED).pack(anchor='w',pady=dp(3))

    startup=card(settings,'시작 및 종료')
    app.startup_check=switch_row(startup,'Windows 로그인 시 자동 실행',app.startup_enabled,command=app.change_startup)
    import sys
    if sys.platform!='win32' or app.startup_error: app.startup_check.configure(state='disabled')
    switch_row(startup,'시작 시 트레이로 최소화',app.start_minimized,'창을 열지 않고 알림 영역에서 실행합니다.',app.save_config)
    switch_row(startup,'창을 닫으면 트레이로 최소화',app.close_to_tray,'끄면 닫기(X)를 눌렀을 때 앱이 종료됩니다.',app.save_config)
    switch_row(startup,'저장된 기기에 자동 연결',app.auto_connect,'앱을 시작할 때 마지막 기기에 연결합니다.',app.save_config)
    overlay=card(settings,'볼륨 알림')
    switch_row(overlay,'볼륨 오버레이 표시',app.overlay_enabled,'스피커 노브를 돌리면 현재 볼륨을 표시합니다.',app.save_config)
    action(overlay,'미리 보기',lambda:app.show_overlay(app.state.get('volume',13),True),connected=False,side='right')
    row=line(settings,pady=(0,8))
    text(row,'설정은 자동 저장됩니다. 시작 옵션은 다음 실행부터 적용됩니다.',9,MUTED).pack(side='left')
    action(row,'앱 종료',app.quit,connected=False,side='right')
    if app.startup_error: text(settings,'자동 실행 설정을 읽지 못했습니다: '+app.startup_error,9,MUTED).pack(anchor='w')

    book.select(0)
    app.help_popover.install()
    app.update_controls()
