"""Consistent, antialiased line icons; no platform-dependent emoji glyphs."""
import math
from PIL import Image,ImageDraw,ImageTk


def icon_image(master,name,color='#f5f5f5',size=20):
    scale=4
    img=Image.new('RGBA',(size*scale,size*scale))
    draw=ImageDraw.Draw(img)
    unit=size*scale/24
    def points(coords): return [round(v*unit) for v in coords]
    def line(coords,width=1.6): draw.line(points(coords),fill=color,width=max(1,round(width*unit)),joint='curve')
    def oval(coords,fill=False,width=1.6): draw.ellipse(points(coords),fill=color if fill else None,outline=color,width=max(1,round(width*unit)))
    def rect(coords): draw.rectangle(points(coords),outline=color,width=max(1,round(1.5*unit)))
    if name in ('eq','tune'):
        for a,b in ((5,8),(12,16),(19,10)):
            if name=='eq':
                line((a,3,a,21)); rect((a-2,b-2,a+2,b+2))
            else:
                line((3,a,21,a)); oval((b-2,a-2,b+2,a+2),True)
    elif name=='music':
        line((10,17,10,5,20,3,20,15));line((10,8,20,6));oval((4,16,10,21),True);oval((14,14,20,19),True)
    elif name=='monitor':
        draw.arc(points((5,3,20,20)),180,355,fill=color,width=round(1.6*unit))
        draw.arc(points((9,7,17,15)),170,365,fill=color,width=round(1.6*unit))
        line((5,11,5,17,8,21,12,21));line((14,13,12,17))
    elif name=='speaker':
        rect((6,2,18,22));oval((10,5,14,9));oval((9,13,15,19))
    elif name=='volume':
        line((3,9,7,9,12,5,12,19,7,15,3,15,3,9))
        draw.arc(points((9,7,19,17)),290,70,fill=color,width=round(1.6*unit))
        draw.arc(points((8,3,23,21)),290,70,fill=color,width=round(1.6*unit))
    elif name=='settings':
        coords=[]
        for i in range(24):
            angle=math.pi*i/12
            r=10 if i%3!=1 else 8
            coords.extend((12+r*math.cos(angle),12+r*math.sin(angle)))
        coords.extend(coords[:2]);line(coords);oval((8,8,16,16))
    elif name=='bluetooth':
        line((7,6,18,16,12,21,12,3,18,8,7,18))
    elif name=='back': line((15,4,7,12,15,20))
    elif name=='chevron': line((9,5,16,12,9,19))
    elif name=='check': line((4,12,9,17,20,6),2)
    elif name=='edit':
        line((5,15,16,4,20,8,9,19,4,20,5,15));line((14,6,18,10))
    elif name=='save':
        line((4,3,18,3,21,6,21,21,3,21,3,3,4,3));rect((7,3,16,9));rect((7,14,17,21))
    elif name=='folder': line((2,6,9,6,11,9,22,9,19,20,3,20,2,6));line((3,11,20,11))
    elif name=='refresh':
        draw.arc(points((4,4,20,20)),45,320,fill=color,width=round(1.6*unit));line((20,3,20,8,15,8))
    elif name=='power':
        draw.arc(points((4,4,20,21)),305,235,fill=color,width=round(1.7*unit));line((12,2,12,12))
    elif name=='close': line((5,5,19,19));line((19,5,5,19))
    elif name=='link':
        draw.arc(points((3,3,15,15)),100,350,fill=color,width=round(1.6*unit))
        draw.arc(points((9,9,21,21)),280,170,fill=color,width=round(1.6*unit));line((8,16,16,8))
    elif name=='home': line((3,10,12,3,21,10));line((6,9,6,21,18,21,18,9));rect((10,14,14,21))
    return ImageTk.PhotoImage(img.resize((size,size),Image.Resampling.LANCZOS),master=master)


BUTTON_ICONS={
    '연결':'link','연결 해제':'close','기기 선택':'bluetooth','기기 선택…':'bluetooth','취소':'close',
    '적용':'check','EQ 적용':'check','튜닝 적용':'check','안내음 적용':'check','어쿠스틱 튜닝 적용':'check',
    '저장':'save','이름 저장':'edit','파일 저장':'save','불러오기':'folder','0dB로 편집':'refresh',
    '백업 복원':'refresh','새로 읽기':'refresh','다시 검색':'refresh','미리 보기':'volume','앱 종료':'power',
    '모니터':'monitor','음악':'music','사용자 설정':'eq','선택한 기기에 연결':'link',
}
