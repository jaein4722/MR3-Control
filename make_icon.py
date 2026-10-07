"""Render the simple speaker glyph used for the window and notification area."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.deps'))
from PIL import Image,ImageDraw


def main():
    scale=4
    img=Image.new('RGBA',(256*scale,256*scale),(0,0,0,0))
    d=ImageDraw.Draw(img)
    def box(coords): return tuple(int(x*scale) for x in coords)
    d.rounded_rectangle(box((8,8,248,248)),radius=48*scale,fill='#202020')
    d.rounded_rectangle(box((66,31,190,225)),radius=12*scale,fill='#080808',outline='#dfbf7c',width=5*scale)
    d.ellipse(box((109,51,147,89)),fill='#f5f5f5')
    d.ellipse(box((84,108,172,196)),outline='#dfbf7c',width=7*scale)
    d.ellipse(box((106,130,150,174)),fill='#dfbf7c')
    img=img.resize((256,256),Image.Resampling.LANCZOS)
    folder=ROOT/'assets'
    folder.mkdir(exist_ok=True)
    img.save(folder/'mr3.png')
    img.save(folder/'mr3.ico',sizes=[(16,16),(20,20),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])


if __name__=='__main__': main()
