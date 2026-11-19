#!/usr/bin/env python3
"""Ember's original 40-second motion film, built from isolated GTK captures.

Requires Pillow, NumPy and FFmpeg. No browser/account/session is read.
Inputs come from capture_promo.py and promo_audio.py; all demo media is original.
"""
import argparse
from functools import lru_cache
import math
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, LENGTH = 1920, 1080, 60, 40
GOLD = (232, 187, 112)
IVORY = (244, 233, 210)
MUTED = (177, 169, 150)
COPY = {
 'ru': [
  ('Твоя музыка.\nЧуть теплее.', 'Spotify · Apple Music\nYouTube · Яндекс Музыка', 'ЗНАКОМСТВО С EMBER', ''),
  ('Четыре источника.\nОдно пространство.', 'Открой меню источника\nв шапке плеера.', '01  /  ВЫБОР ИСТОЧНИКА', 'Spotify  ·  Apple Music  ·  YouTube  ·  Яндекс'),
  ('Твои аккаунты —\nвнутри плеера.', 'Настройки / Плеер /\nАккаунты и вход', '02  /  ПОДКЛЮЧЕНИЕ', 'Условия подписок зависят от сервиса'),
  ('Найти. Выбрать.\nСлушать.', 'Название песни\nили исполнитель.', '03  /  ПОИСК И МУЗЫКА', 'Поиск / трек / воспроизведение'),
  ('Внутри музыки.', 'Большая обложка. Живые лампы.\nТекст песни — по кнопке.', '04  /  ПОЛНЫЙ ЭКРАН', 'F11 — полный экран  ·  Esc — назад'),
  ('Рядом. Даже\nкогда занят.', 'Mini оставляет главное:\nобложку, лампы и управление.', '05  /  КОМПАКТНЫЙ РЕЖИМ', 'Кнопка Mini — в шапке виджета'),
  ('Emberbox Audio', 'Твоя музыка. Чуть теплее.', 'LINUX  /  OPEN SOURCE', 'Установка и подключение — в README'),
 ],
 'en': [
  ('Your music.\nA little warmer.', 'Spotify · Apple Music\nYouTube · Yandex Music', 'MEET EMBER', ''),
  ('Four sources.\nOne space.', 'Open the source menu\nin the player header.', '01  /  CHOOSE YOUR SOURCE', 'Spotify  ·  Apple Music  ·  YouTube  ·  Yandex'),
  ('Your accounts,\ninside the player.', 'Settings / Player /\nAccounts & sign-in', '02  /  CONNECT YOUR MUSIC', 'Service subscriptions have their own terms'),
  ('Search. Choose.\nPlay.', 'Search for a song\nor an artist.', '03  /  FIND YOUR MUSIC', 'Search / choose a track / play'),
  ('Inside the music.', 'Large artwork. Live tubes.\nLyrics when you want them.', '04  /  FULLSCREEN', 'F11 — fullscreen  ·  Esc — back'),
  ('Close by. Even\nwhile you work.', 'Mini keeps the essentials:\nartwork, tubes and controls.', '05  /  MINI MODE', 'Mini is in the widget header'),
  ('Emberbox Audio', 'Your music. A little warmer.', 'LINUX  /  OPEN SOURCE', 'Installation and service setup in the README'),
 ]
}
START = (0, 4, 10, 16, 23, 31, 35)
FILES = ('hero', 'sources', 'accounts', 'search', 'fullscreen', 'mini', 'widget')


def ease(v):
 v = min(1., max(0., v)); return v*v*v*(v*(v*6-15)+10)


@lru_cache(maxsize=30)
def font(size, bold=False):
 name = 'NotoSans-' + ('Bold' if bold else 'Regular') + '.ttf'
 for directory in ('/usr/share/fonts/noto', '/usr/share/fonts/truetype/noto'):
  path=Path(directory)/name
  if path.is_file():return ImageFont.truetype(str(path),size)
 path=subprocess.check_output(['fc-match','-f','%{file}','Noto Sans:style='+('Bold' if bold else 'Regular')],text=True).strip()
 if not path:raise RuntimeError('Install Noto Sans fonts before rendering the film')
 return ImageFont.truetype(path,size)


def text(draw, xy, value, size, color=IVORY, bold=False, spacing=18):
 draw.multiline_text(xy, value, font=font(size, bold), fill=color, spacing=spacing)


def background():
 yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
 warm=np.exp(-(((xx-1490)/720)**2+((yy-620)/610)**2))
 cool=np.exp(-(((xx-390)/870)**2+((yy-50)/470)**2))
 a=np.zeros((H,W,3),np.float32)+np.array([12,16,17])
 a+=warm[...,None]*np.array([21,12,3])+cool[...,None]*np.array([2,5,6])
 return Image.fromarray(np.uint8(np.clip(a,0,255))).convert('RGBA')


def card(image, box, radius=30):
 image=image.convert('RGBA')
 scale=min(box[0]/image.width,box[1]/image.height)
 image=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
 width,height=image.size
 frame=Image.new('RGBA',(width+36,height+36))
 draw=ImageDraw.Draw(frame)
 draw.rounded_rectangle((0,0,width+35,height+35),radius+12,fill=(28,31,31,230),outline=(186,164,127,65),width=1)
 draw.rounded_rectangle((8,8,width+27,height+27),radius+5,fill=(7,10,10,255),outline=(255,235,194,28),width=1)
 mask=Image.new('L',image.size);ImageDraw.Draw(mask).rounded_rectangle((0,0,width-1,height-1),radius,fill=255)
 frame.paste(image,(18,18),mask)
 return frame


class Film:
 def __init__(self, captures, language):
  self.captures=captures;self.language=language;self.bg=background()
  self.stills=[]
  for i,name in enumerate(FILES):
   path=ROOT/'assets/updates/2026-11-18-music-services.png' if name=='hero' else captures/(name+'.png')
   image=Image.open(path).convert('RGBA')
   if name=='accounts' and (captures/'accounts-detail.png').exists():
    image=Image.open(captures/'accounts-detail.png').convert('RGBA')
    image=image.crop((0,0,image.width,image.height-22))
   box=(1060,650) if name=='hero' else (780,700) if name in ('sources','accounts','search') else (1120,690) if name=='fullscreen' else (540,650) if name=='mini' else (630,650)
   self.stills.append(card(image,box))
  source=Image.open(captures/'search.png')
  self.query=card(source.crop((1545,104,1845,172)),(720,164),18)
  self.results=card(source.crop((88,235,1130,563)),(780,320),18)
  self.shadow={}
  self.live=sorted((captures/'live-frames').glob('*.png'))

 @lru_cache(maxsize=100)
 def live_frame(self, index):
  return card(Image.open(self.live[index]),(1120,690))

 def scene(self, i, local):
  layer=Image.new('RGBA',(W,H));draw=ImageDraw.Draw(layer)
  title,body,kicker,note=COPY[self.language][i]
  intro=ease(local/.95)
  dy=round(25*(1-intro))
  text(draw,(126,244+dy),kicker,19,GOLD,True)
  text(draw,(120,306+dy),title,64 if i!=6 else 70,IVORY,True,12)
  text(draw,(126,505+dy if '\n' in title else 420+dy),body,29,MUTED,False,17)
  text(draw,(126,830),note,21,MUTED)
  if i==6:
   draw.rounded_rectangle((122,540,716,612),20,fill=(39,38,30),outline=(177,145,91,110),width=1)
   text(draw,(146,558),'./install.sh --autostart',25,GOLD)
   text(draw,(126,665),'github.com/BlackSnaker/emberbox-audio',20,MUTED)
  asset=self.stills[i]
  if i==3:
   asset=Image.new('RGBA',(816,630))
   asset.alpha_composite(self.query,(0,10))
   result=self.results.copy()
   amount=ease((local-1.1)/.8)
   if amount<1:result.putalpha(result.getchannel('A').point(lambda v:round(v*amount)))
   asset.alpha_composite(result,(0,round(235+20*(1-amount))))
  if i==4 and self.live:
   # The actual captured frame clock and PCM-driven tubes, not painted replicas.
   asset=self.live_frame(min(len(self.live)-1,int(max(0,local-1)*30)))
  if i==4 and local>4.5 and (self.captures/'lyrics.png').is_file():
   asset=Image.blend(asset,self.lyrics,ease((local-4.5)/.9))
  x=round(790+(28*(1-intro))+5*math.sin(local*.5))
  if i in (1,2,3):x=round(1020+(28*(1-intro)))
  if i==4:x=round(740+28*(1-intro))
  if i==5:x=round(1120+28*(1-intro))
  if i==6:x=round(1080+28*(1-intro))
  y=round((H-asset.height)/2+25+6*math.sin(local*.35))
  key=asset.size
  if key not in self.shadow:
   sh=Image.new('RGBA',(asset.width+100,asset.height+100));d=ImageDraw.Draw(sh)
   d.rounded_rectangle((45,50,asset.width+55,asset.height+55),45,fill=(0,0,0,170))
   self.shadow[key]=sh.filter(ImageFilter.GaussianBlur(25))
  layer.alpha_composite(self.shadow[key],(x-50,y-35))
  layer.alpha_composite(asset,(x,y))
  # A tiny editorial cue, outside the actual UI, indicates the next action.
  if i in (1,2,3,5):
   labels={'ru':('Источник','Аккаунты и вход','Поиск','Mini'),'en':('Source','Accounts & sign-in','Search','Mini')}
   value=labels[self.language][(1,2,3,5).index(i)]
   tw=draw.textlength(value,font=font(19,True));bx=x+25;by=max(182,y-61)
   draw.rounded_rectangle((bx,by,bx+tw+44,by+39),19,fill=(42,40,31,255),outline=(208,172,105,110))
   text(draw,(bx+22,by+5),value,19,GOLD,True)
  return layer

 def prepare(self):
  self.lyrics=card(Image.open(self.captures/'lyrics.png'),(1120,690))

 def frame(self,t):
  image=self.bg.copy()
  i=max(n for n,s in enumerate(START) if s<=t)
  local=t-START[i]
  if i>0 and local<.85:
   amount=ease(local/.85)
   previous=self.scene(i-1,START[i]-START[i-1]+local)
   current=self.scene(i,local)
   image.alpha_composite(Image.blend(previous,current,amount))
  else:image.alpha_composite(self.scene(i,local))
  overlay=Image.new('RGBA',(W,H));draw=ImageDraw.Draw(overlay)
  text(draw,(126,79),'E M B E R',28,GOLD,True)
  text(draw,(126,126),'GRUNESPHISM  /  MUSIC, MADE WARM',13,MUTED)
  text(draw,(W-315,87),'PRODUCT FILM  /  00:40',15,MUTED)
  # Restrained copper glints breathe slowly, away from copy and screenshots.
  for n in range(12):
   x=70+(n*157+t*(3 if n%2 else -2))%(W-140)
   y=210+(n*113)%(H-390)+5*math.sin(t*.45+n)
   a=round(18+12*(.5+.5*math.sin(t*.6+n)))
   draw.ellipse((x,y,x+2,y+2),fill=(*GOLD,a))
  draw.line((126,950,W-126,950),fill=(225,200,153,35),width=1)
  draw.line((126,950,126+(W-252)*t/LENGTH,950),fill=(*GOLD,165),width=2)
  text(draw,(126,975),'LINUX  ·  SPOTIFY / APPLE MUSIC / YOUTUBE / YANDEX MUSIC',14,MUTED)
  text(draw,(W-520,975),'Original demo media · independent project',13,MUTED)
  image.alpha_composite(overlay)
  # Fade only through the same dark material, avoiding bright transition flashes.
  fade=ease((LENGTH-t)/1.1)
  if fade<1:image=Image.blend(self.bg,image,fade)
  return image.convert('RGB')


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--captures',type=Path,required=True)
 p.add_argument('--audio',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 p.add_argument('--language',choices=('ru','en'),default='ru')
 p.add_argument('--storyboard',action='store_true',help='Only render representative frames')
 args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 def stamp(seconds):
  ms=round(seconds*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
 subtitles=[]
 for n,start in enumerate(START):
  end=START[n+1] if n+1<len(START) else LENGTH
  title,body,_kicker,_note=COPY[args.language][n]
  subtitles.append(f'{n+1}\n{stamp(start)} --> {stamp(end)}\n{title.replace(chr(10), " ")}\n{body}\n')
 (args.output/f'ember-introduction.{args.language}.srt').write_text('\n'.join(subtitles))
 film=Film(args.captures,args.language);film.prepare()
 for n,t in enumerate((2.8,7.5,13,19.5,26,33,37.5)):
  film.frame(t).save(args.output/f'story-{args.language}-{n}.jpg',quality=92)
 film.frame(0).save(args.output/f'poster-{args.language}.png')
 if args.storyboard:return
 target=args.output/f'ember-introduction.{args.language}.mp4'
 command=['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
          '-i',str(args.audio),'-map','0:v','-map','1:a','-t',str(LENGTH),'-c:v','libx264','-preset','fast','-crf','21',
          '-maxrate','1600k','-bufsize','3200k','-pix_fmt','yuv420p','-threads','3','-c:a','aac','-b:a','128k','-ar','48000',
          '-movflags','+faststart','-metadata','title=Emberbox Audio — Your music, a little warmer.',
          '-metadata','comment=Original GTK demo captures, artwork and synthesized soundtrack. Independent project.',str(target)]
 with subprocess.Popen(command,stdin=subprocess.PIPE) as encoder:
  try:
   for n in range(FPS*LENGTH):
    encoder.stdin.write(film.frame(n/FPS).tobytes())
    if n%(FPS*5)==0:print(f'{args.language}: {n/FPS:.0f}/{LENGTH}s',flush=True)
  finally:encoder.stdin.close()
  if encoder.wait():raise SystemExit('FFmpeg export failed')
 print(target,round(target.stat().st_size/1_000_000,2),'MB',flush=True)
 if target.stat().st_size>=9_900_000:raise SystemExit('Video exceeds the GitHub free upload budget')


if __name__=='__main__':main()
