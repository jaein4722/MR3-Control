"""BLE discovery UI: saved identity and this scan's observations stay separate."""
import tkinter as tk
from tkinter import ttk
import re
from mr3_dpi import dp
from mr3_widgets import BG,CARD,FG,MUTED,ACCENT,text,button,Toggle


def saved_devices(config):
    """Migrate the old single-device identity without losing previously saved MR3s."""
    found={}
    items=config.get('devices',[])
    if not isinstance(items,list): items=[]
    if config.get('device_name') and config.get('address'):
        items=[*items,{'address':config['address'],'name':config['device_name']}]
    for item in items:
        if not isinstance(item,dict): continue
        address=str(item.get('address','')).strip().upper()
        if re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}',address):
            found[address]={'address':address,'name':str(item.get('name') or 'MR3')}
    return found


def pairing_label(address, pairing):
    if pairing.get('status') == 'complete':
        return '페어링됨' if address in pairing.get('devices', {}) else '미페어링'
    return '페어링 확인 실패' if pairing.get('status') == 'error' else '페어링 확인 중'


def device_groups(config, rows, pairing, state):
    """Bond status is OS evidence, never inferred from app connection history."""
    known = saved_devices(config)
    found = {r['address']: r for r in rows}
    paired = pairing.get('devices', {}) if pairing.get('status') == 'complete' else {}
    groups = {key: [] for key in ('paired', 'saved', 'candidates', 'others')}
    for address in dict.fromkeys([*known, *paired, *found]):
        row = found.get(address)
        item = known.get(address) or row or paired[address]
        name = item['name']
        names = name.upper() + ' ' + paired.get(address, {}).get('name', '').upper()
        candidate = address in known or bool(row and row['candidate']) or any(
            word in names for word in ('EDIFIER', 'MR3'))
        group = ('paired' if address in paired else 'saved' if address in known else 'candidates') if candidate else 'others'
        connected = state.get('connected') and state.get('address') == address
        observation = '연결됨' if connected else '검색됨' if row else '검색 미발견'
        kind = f'{pairing_label(address, pairing)} · {observation}'
        if not candidate: kind += ' · 연결 미지원'
        groups[group].append((address, name, kind, f"{row['rssi']} dBm" if row else '—'))
    return groups


class DevicePicker(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app.root)
        self.app=app
        self.title('MR3 기기 선택')
        self.geometry(f'{dp(840)}x{dp(670)}')
        self.minsize(dp(760),dp(640))
        self.configure(bg=BG)
        self.transient(app.root)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Escape>',lambda _:self.close())
        self.data=app.discovery
        self.animating=False
        self.show_others=tk.BooleanVar(self,value=True)
        frame=tk.Frame(self,bg=BG,padx=dp(24),pady=dp(20))
        frame.pack(fill='both',expand=True)
        text(frame,'기기 선택',18).pack(anchor='w')
        text(frame,'주변에서 BLE 신호를 보내는 기기를 12초 동안 찾습니다.',11).pack(anchor='w',pady=dp((8,4)))
        text(frame,'처음 연결 시 제어용 BLE 페어링을 진행합니다. 페어링 후에도 연결이 실패할 수 있습니다.\n'
                   '휴대폰 등과의 블루투스 오디오 연결이 필요할 수 있습니다. 다른 제어 앱은 연결 해제해 주세요.',
             10,MUTED,wraplength=dp(700),justify='left').pack(anchor='w')

        saved=tk.Frame(frame,bg=CARD,padx=dp(16),pady=dp(12))
        saved.pack(fill='x',pady=dp((18,16)))
        copy=tk.Frame(saved,bg=CARD)
        copy.pack(side='left',fill='x',expand=True)
        self.saved_name=text(copy,'',12)
        self.saved_name.pack(anchor='w')
        self.saved_detail=text(copy,'',9,MUTED)
        self.saved_detail.pack(anchor='w',pady=dp((5,0)))
        self.saved_connect=button(saved,'최근 기기 연결',self.connect_saved,icon='link')
        self.saved_connect.pack(side='right',padx=dp((12,0)))

        toolbar=tk.Frame(frame,bg=BG)
        toolbar.pack(fill='x')
        self.search_button=button(toolbar,'다시 검색',app.start_discovery,icon='refresh')
        self.search_button.pack(side='left')
        self.cancel_button=button(toolbar,'검색 취소',app.cancel_connection,icon='close')
        self.cancel_button.pack(side='left',padx=dp(8))
        Toggle(toolbar,self.show_others,self.refresh_rows).pack(side='right')
        text(toolbar,'기타 BLE 기기도 표시',10,MUTED).pack(side='right',padx=dp(10))
        self.scan_status=text(frame,'',10,ACCENT,wraplength=dp(770))
        self.scan_status.pack(fill='x',pady=dp((12,6)))
        style=ttk.Style(self)
        style.configure('Discovery.Horizontal.TProgressbar',background=ACCENT,troughcolor=CARD,
                        borderwidth=0,lightcolor=ACCENT,darkcolor=ACCENT)
        self.progress=ttk.Progressbar(frame,mode='indeterminate',style='Discovery.Horizontal.TProgressbar')
        self.progress.pack(fill='x',pady=dp((0,10)))

        table=tk.Frame(frame,bg=BG)
        table.pack(fill='both',expand=True)
        self.tree=ttk.Treeview(table,columns=('address','kind','rssi'),show='tree headings',height=4,selectmode='browse')
        for key,title,width in (('#0','기기',245),('address','BLE 주소',160),
                                ('kind','페어링 / 검색 상태',215),('rssi','신호',70)):
            self.tree.heading(key,text=title)
            self.tree.column(key,width=dp(width),minwidth=dp(65),stretch=key in ('#0','kind'))
        self.tree.tag_configure('group',foreground=ACCENT)
        for group in ('paired','saved','candidates','others'):
            self.tree.insert('','end',iid=group,text='',open=True,tags=('group',))
        scroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        self.tree.pack(side='left',fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.update_controls())
        self.tree.bind('<Double-1>',lambda _:self.connect_selected())
        self.tree.bind('<Return>',lambda _:self.connect_selected())
        self.hint=text(frame,'',10,MUTED,wraplength=dp(770),justify='left')
        self.hint.pack(fill='x',pady=dp((10,12)))
        footer=tk.Frame(frame,bg=BG)
        footer.pack(fill='x')
        self.pairing_notice=text(footer,'',9,MUTED,wraplength=dp(460),justify='left')
        self.pairing_notice.pack(side='left',fill='x',expand=True,padx=dp((0,12)))
        self.connect_button=button(footer,'선택한 기기에 연결',self.connect_selected,primary=True,icon='link')
        self.connect_button.pack(side='right')
        self.render(self.data)

    def render(self,data):
        self.data=data
        scanning=data['status']=='scanning'
        if scanning and not self.animating:
            self.progress.configure(mode='indeterminate',value=0)
            self.progress.start(30)
        elif not scanning:
            self.progress.stop()
            self.progress.configure(mode='determinate',value=100 if data['status']=='complete' else 0)
        self.animating=scanning
        self.refresh_rows()
        self.refresh_saved()
        self.update_controls()

    def refresh_saved(self):
        address=self.app.address.get().strip().upper()
        connected=self.app.state.get('connected') and self.app.state.get('address')==address
        found=any(r['address']==address for r in self.data['rows'])
        state='현재 연결됨' if connected else '이번 검색에서 발견됨' if found else '이번 검색에서 발견되지 않음'
        self.saved_name.configure(text=self.app.config.get('device_name','저장된 MR3') if address else '저장된 기기 없음')
        paired=pairing_label(address,getattr(self.app,'pairing',{}))
        self.saved_detail.configure(text=f'{address}  ·  {paired}  ·  {state}' if address else '목록에서 MR3를 선택해 연결하세요.')
        self.saved_connect.configure(text='현재 연결됨' if connected else '  최근 기기 연결')

    def refresh_rows(self):
        rows=self.data['rows']
        known=saved_devices(self.app.config)
        groups=device_groups(self.app.config,rows,getattr(self.app,'pairing',{}),self.app.state)
        labels={'paired':'페어링된 기기', 'saved':'저장된 기기 · 페어링 미확인/미등록',
                'candidates':'MR3 / Edifier 후보', 'others':'기타 BLE 기기 · 연결 미지원'}
        self.connectable={r[0] for group in ('paired','saved','candidates') for r in groups[group]}
        visible={r[0] for group,items in groups.items() for r in items if group!='others' or self.show_others.get()}
        # Move existing rows between groups without losing the user's selection.
        for group in groups:
            for address in self.tree.get_children(group):
                if address not in visible: self.tree.delete(address)
        for group,items in groups.items():
            self.tree.item(group,text=f'{labels[group]} ({len(items)})')
            if group=='saved' and not items:
                self.tree.detach(group)
            else:
                self.tree.move(group,'',list(groups).index(group))
            shown=items if group!='others' or self.show_others.get() else []
            for i,(address,name,kind,rssi) in enumerate(shown):
                values=(address,kind,rssi)
                if self.tree.exists(address): self.tree.item(address,text=name,values=values)
                else: self.tree.insert(group,'end',iid=address,text=name,values=values)
                self.tree.move(address,group,i)
        candidates=sum(r['candidate'] or r['address'] in known for r in rows)
        count=f"이번 검색 {len(rows)}대 · MR3/Edifier 후보 {candidates}대"
        status=self.data['status']
        prefix={'idle':'검색 대기','scanning':'검색 중… (12초)', 'complete':'검색 완료',
                'cancelled':'검색 취소 · 일부 결과','error':'검색 실패 · 일부 결과'}[status]
        timestamp=f" · {self.data.get('time','')}" if status in ('complete','cancelled','error') else ''
        self.scan_status.configure(text=f'{prefix}{timestamp}  |  {count}')
        if status=='error':
            hint='검색 오류: '+str(self.data.get('error','알 수 없는 오류'))
        elif not candidates and rows:
            hint='이번 검색에서는 MR3/Edifier 후보를 찾지 못했습니다.'
            if not self.show_others.get(): hint+=' 기타 BLE 기기도 표시하면 전체 결과를 볼 수 있습니다.'
        elif not rows:
            hint='아직 발견된 기기가 없습니다.' if status=='scanning' else '이번 검색에서 BLE 신호를 발견하지 못했습니다.' if status!='idle' else '검색을 시작하면 발견된 기기가 여기에 표시됩니다.'
        else:
            hint='분류는 기기의 BLE 이름과 식별 신호 기준입니다. MR3 지원 여부는 연결 시 확인합니다.'
        if status!='error': hint+=' 저장된 MR3는 검색에 없어도 위 버튼으로 연결할 수 있습니다.'
        self.hint.configure(text=hint)
        self.update_controls()

    def update_controls(self):
        busy=self.app.busy
        self.search_button.configure(state='disabled' if busy else 'normal')
        self.cancel_button.configure(state='normal' if busy and self.app.action=='discover' else 'disabled')
        selected=self.tree.selection()
        allowed=bool(selected and selected[0] in getattr(self,'connectable',set()))
        pairing=getattr(self.app,'pairing',{})
        target=selected[0] if allowed else self.app.address.get().strip().upper()
        status=pairing_label(target,pairing)
        if selected and selected[0] not in ('paired','saved','candidates','others') and not allowed:
            notice='이 앱에서 지원하지 않는 기기입니다.'
            label='선택한 기기에 연결'
        elif status=='미페어링':
            notice='연결하면 제어용 BLE 페어링을 자동으로 진행합니다.\n오디오 출력 설정은 변경하지 않습니다.'
            label='페어링 후 연결' if allowed else '선택한 기기에 연결'
        elif status=='페어링됨':
            notice='Windows에 페어링된 기기입니다. 저장된 기록으로 연결을 시도합니다.'
            label='선택한 기기에 연결'
        else:
            notice='연결 시 페어링 기록을 확인하고, 없으면 자동으로 등록합니다.'
            if pairing.get('status')=='error': notice='페어링 상태 확인 실패 · 다시 검색해 갱신하세요.\n'+notice
            label='선택한 기기에 연결'
        self.pairing_notice.configure(text=notice)
        self.connect_button.configure(text=label,state='normal' if not busy and allowed else 'disabled')
        same=self.app.state.get('connected') and self.app.state.get('address')==self.app.address.get().strip().upper()
        self.saved_connect.configure(state='normal' if not busy and self.app.address.get().strip() and not same else 'disabled')

    def connect_saved(self):
        if self.app.busy: return
        self.destroy()
        self.app.connect()

    def connect_selected(self):
        if self.app.busy or not self.tree.selection() or self.tree.selection()[0] not in self.connectable: return
        self.app.address.set(self.tree.selection()[0])
        self.destroy()
        self.app.connect()

    def close(self):
        if self.app.action=='discover': self.app.cancel_connection()
        self.destroy()

    def destroy(self):
        self.progress.stop()
        super().destroy()
