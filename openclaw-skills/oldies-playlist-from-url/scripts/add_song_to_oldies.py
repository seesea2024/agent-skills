#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, json, os, re, shutil, subprocess, sys, time, unicodedata
from pathlib import Path
import requests
W=Path('/Users/stone/.openclaw/workspace'); DL=W/'music-downloads'/'url-songs'; EX=W/'music-exports'; BK=W/'music-backups'
UA='OpenClaw local music organizer'
def sh(cmd,timeout=120):
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
 if p.returncode: raise RuntimeError(p.stderr or p.stdout)
 return p.stdout.rstrip('\n')
def osa(sc,args=None,timeout=120):
 return sh(['osascript','-e',sc]+(args or []),timeout)
def esc(s): return (s or '').replace('\\','\\\\').replace('"','\\"')
def headers(): return ['--no-update','--referer','https://www.bilibili.com/','--user-agent','Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36','--add-header','Origin:https://www.bilibili.com','--add-header','Accept-Language:zh-CN,zh;q=0.9,en;q=0.8']
def safe(s):
 s=unicodedata.normalize('NFC',s); s=re.sub(r'[/:\\*?"<>|\n\r\t]+',' ',s); s=re.sub(r'\s+',' ',s).strip(); return s[:170] or 'untitled'
def info(url): return json.loads(sh(['yt-dlp',*headers(),'--dump-json','--no-playlist',url],90))
def infer(i):
 t=(i.get('title') or '').strip(); m=re.search(r'([^《》|｜\-—_]{2,24})《([^》]{1,80})》',t)
 if m: return m.group(2).strip(),m.group(1).strip()
 return t,''
def snap(pl,label):
 BK.mkdir(parents=True,exist_ok=True); path=BK/f'{pl}-{label}-{dt.datetime.now():%Y%m%d-%H%M%S}.tsv'
 sc=f'''tell application "Music"
set targetName to "{esc(pl)}"
set out to "index\\tname\\tartist\\tlyrics_chars\\tpersistent_id\\tlocation\\n"
repeat with p in user playlists
if name of p is targetName then
set i to 1
repeat with t in tracks of p
set locText to ""
try
set locText to POSIX path of (location of t as alias)
end try
set lyr to ""
try
set lyr to lyrics of t as text
end try
set out to out & i & "\\t" & (name of t as text) & "\\t" & (artist of t as text) & "\\t" & (length of lyr) & "\\t" & (persistent ID of t as text) & "\\t" & locText & "\\n"
set i to i + 1
end repeat
return out
end if
end repeat
return "NOT_FOUND"
end tell'''
 path.write_text(osa(sc,timeout=60),encoding='utf-8'); return path
def download(url):
 DL.mkdir(parents=True,exist_ok=True); out=str(DL/'%(title).200B [%(id)s].%(ext)s')
 sh(['yt-dlp',*headers(),'--no-playlist','-x','--audio-format','mp3','--audio-quality','0','-o',out,url],600)
 return sorted(DL.glob('*.mp3'),key=lambda p:p.stat().st_mtime,reverse=True)[0]
def find_track(pl,title,artist,source):
 sc=f'''tell application "Music"
set targetName to "{esc(pl)}"
repeat with p in user playlists
if name of p is targetName then
repeat with t in tracks of p
set c to ""
try
set c to comment of t as text
end try
if "{esc(source or '')}" is not "" and c contains "{esc(source or '')}" then return persistent ID of t as text
if (name of t as text) is "{esc(title)}" and (artist of t as text) is "{esc(artist)}" then return persistent ID of t as text
end repeat
end if
end repeat
return ""
end tell'''
 return osa(sc,timeout=30).strip() or None
def import_track(mp3,pl,title,artist,album,genre,source,url):
 pid=find_track(pl,title,artist,source)
 if not pid:
  sc=f'''set mp3Path to POSIX file "{esc(str(mp3))}" as alias
set targetName to "{esc(pl)}"
tell application "Music"
set targetPlaylist to missing value
repeat with p in user playlists
if name of p is targetName then set targetPlaylist to p
end repeat
if targetPlaylist is missing value then return "PLAYLIST_NOT_FOUND"
add mp3Path to targetPlaylist
return "ADDED"
end tell'''
  out=osa(sc,timeout=90)
  if out=='PLAYLIST_NOT_FOUND': raise RuntimeError('playlist not found')
  time.sleep(1)
  sc=f'''tell application "Music"
set targetName to "{esc(pl)}"
repeat with p in user playlists
if name of p is targetName then
repeat with t in tracks of p
set locText to ""
try
set locText to POSIX path of (location of t as alias)
end try
if locText contains "{esc(mp3.name)}" then return persistent ID of t as text
end repeat
end if
end repeat
return ""
end tell'''
  pid=osa(sc,timeout=60).strip()
  if not pid: raise RuntimeError('new track pid not found')
 comment=f'Source: {source or url}; downloaded {dt.datetime.now():%Y-%m-%d}'
 sc=f'''tell application "Music"
set matches to (every track of library playlist 1 whose persistent ID is "{esc(pid)}")
if (count of matches) is 0 then return "MISS"
set t to item 1 of matches
set name of t to "{esc(title)}"
set artist of t to "{esc(artist)}"
set album of t to "{esc(album)}"
set genre of t to "{esc(genre)}"
set comment of t to "{esc(comment)}"
return persistent ID of t as text
end tell'''
 return osa(sc,timeout=60)
def clean_lrc(x):
 out=[]
 for line in (x or '').splitlines():
  line=re.sub(r'(\[[0-9:.]+\])+','',line).strip()
  if line and not re.match(r'^(作词|作曲|编曲|制作人|监制|出品|发行|OP|SP|版权|Copyright)\s*[:：]',line,re.I): out.append(line)
 return '\n'.join(out).strip()
def lyrics(title,artist):
 # LRCLIB exact/high confidence
 best=('', '', -999)
 for params in [{'track_name':title,'artist_name':artist},{'track_name':title},{'q':f'{title} {artist}'.strip()}]:
  try: items=requests.get('https://lrclib.net/api/search',params=params,headers={'User-Agent':UA},timeout=20).json()
  except Exception: items=[]
  for it in items:
   text=(it.get('plainLyrics') or clean_lrc(it.get('syncedLyrics') or '')).strip();
   if not text or it.get('instrumental'): continue
   tn=(it.get('trackName') or '').lower(); an=(it.get('artistName') or '').lower(); score=0
   if tn==title.lower(): score+=50
   elif title.lower() in tn: score+=30
   for part in re.split(r'[,/&／&\s]+',artist.lower()):
    if part and part in an: score+=15
   score+=20
   if score>best[2]: best=(text,f"LRCLIB:{it.get('trackName')} / {it.get('artistName')}",score)
 if best[0] and best[2]>=70: return best
 # NetEase fallback
 h={'User-Agent':'Mozilla/5.0','Referer':'https://music.163.com/'}
 try: songs=requests.post('https://music.163.com/api/search/get/web',data={'s':f'{title} {artist}'.strip(),'type':1,'limit':10,'offset':0},headers=h,timeout=20).json().get('result',{}).get('songs',[])
 except Exception: songs=[]
 bs=None; bsc=-999
 for s in songs:
  name=s.get('name') or ''; arts=','.join(a.get('name','') for a in s.get('artists',[])); score=(50 if name==title else 30 if title in name else 0)
  for part in re.split(r'[,/&／&\s]+',artist):
   if part and part in arts: score+=15
  if score>bsc: bs=s; bsc=score
 if bs and bsc>=50:
  sid=bs['id']; text=clean_lrc(requests.get('https://music.163.com/api/song/lyric',params={'id':sid,'lv':1,'kv':1,'tv':-1},headers=h,timeout=20).json().get('lrc',{}).get('lyric') or '')
  if text: return text,f"NetEase:{sid}:{bs.get('name')}",bsc
 return '','',-999
def set_lyrics(pid,text):
 sc='''on run argv
set pid to item 1 of argv
set lyr to item 2 of argv
tell application "Music"
set matches to (every track of library playlist 1 whose persistent ID is pid)
if (count of matches) > 0 then
set lyrics of (item 1 of matches) to lyr
return "OK"
else
return "MISS"
end if
end tell
end run'''
 return osa(sc,[pid,text],timeout=60)
def rows(pl):
 sc=f'''tell application "Music"
set targetName to "{esc(pl)}"
set out to "index\\tname\\tartist\\tduration\\tpersistent_id\\tlocation\\n"
repeat with p in user playlists
if name of p is targetName then
set i to 1
repeat with t in tracks of p
set locText to ""
try
set locText to POSIX path of (location of t as alias)
end try
set out to out & i & "\\t" & (name of t as text) & "\\t" & (artist of t as text) & "\\t" & (duration of t as text) & "\\t" & (persistent ID of t as text) & "\\t" & locText & "\\n"
set i to i + 1
end repeat
return out
end if
end repeat
return "NOT_FOUND"
end tell'''
 out=[]
 for line in osa(sc,timeout=60).splitlines()[1:]:
  p=line.split('\t')
  if len(p)>=6: out.append({'name':p[1],'artist':p[2],'duration':p[3],'pid':p[4],'location':p[5]})
 return out
def get_lyr(pid):
 sc='''on run argv
set pid to item 1 of argv
tell application "Music"
set matches to (every track of library playlist 1 whose persistent ID is pid)
if (count of matches) > 0 then
try
return lyrics of (item 1 of matches) as text
on error
return ""
end try
else
return ""
end if
end tell
end run'''
 return osa(sc,[pid],timeout=30)
def export_all(pl):
 rs=rows(pl); total=len(rs); upd='on run argv\nset totalCount to item 1 of argv as integer\ntell application "Music"\n'
 for n,r in enumerate(rs,1): upd+=f'set matches to (every track of library playlist 1 whose persistent ID is "{esc(r["pid"])}")\nif (count of matches)>0 then\nset t to item 1 of matches\nset track number of t to {n}\nset track count of t to totalCount\nset disc number of t to 1\nset disc count of t to 1\nend if\n'
 upd+='end tell\nreturn "OK"\nend run'; osa(upd,[str(total)],60); time.sleep(1); rs=rows(pl)
 EX.mkdir(parents=True,exist_ok=True); BK.mkdir(parents=True,exist_ok=True); ld=EX/f'{pl}-lyrics'; m3u=EX/f'{pl}.m3u'; stamp=f'{dt.datetime.now():%Y%m%d-%H%M%S}'
 if ld.exists(): shutil.move(str(ld),str(BK/f'{pl}-lyrics-previous-{stamp}'))
 ld.mkdir(parents=True,exist_ok=True); m=['#EXTM3U']; missp=[]; missl=[]; idx=[]
 for n,r in enumerate(rs,1):
  dur=int(float(r['duration'])) if r['duration'] else -1; display=f"{r['artist']} - {r['name']}" if r['artist'] else r['name']; m += [f'#EXTINF:{dur},{display}',r['location']]
  if not os.path.exists(r['location']): missp.append(r['name'])
  ly=get_lyr(r['pid']);
  if not ly.strip(): missl.append(r['name'])
  (ld/safe(f'{n:02d} {r["name"]} - {r["artist"]}.txt')).write_text(f'标题：{r["name"]}\n歌手：{r["artist"]}\n专辑：{pl}\n曲目：{n}/{len(rs)}\n来源：macOS Music 歌词字段\n\n'+ly,encoding='utf-8')
  idx.append(f'{n:02d}. {r["name"]} — {r["artist"]}')
 (ld/'00-目录.txt').write_text('\n'.join(idx)+'\n',encoding='utf-8'); m3u.write_text('\n'.join(m)+'\n',encoding='utf-8')
 return len(rs),m3u,ld,missp,missl,idx
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('url'); ap.add_argument('--title'); ap.add_argument('--artist'); ap.add_argument('--genre',default='国语经典'); ap.add_argument('--playlist',default='老歌精选-2026'); ap.add_argument('--album'); ap.add_argument('--source-id'); ap.add_argument('--dry-run',action='store_true')
 a=ap.parse_args();
 for t in ['yt-dlp','ffmpeg']:
  if not shutil.which(t): raise SystemExit(f'missing {t}')
 inf=info(a.url); title,artist=(a.title,a.artist) if (a.title and a.artist) else infer(inf); title=a.title or title; artist=a.artist or artist; album=a.album or a.playlist; source=a.source_id or inf.get('id')
 print('source_title',inf.get('title')); print('title',title); print('artist',artist); print('source_id',source)
 if a.dry_run: return
 snap(a.playlist,'before-add-url'); mp3=download(a.url); print('mp3',mp3)
 pid=import_track(mp3,a.playlist,title,artist,album,a.genre,source,a.url); print('pid',pid)
 ly,src,score=lyrics(title,artist); print('lyrics_source',src,'score',score,'chars',len(ly))
 if len(ly)<40 or score<50: raise SystemExit('low confidence lyrics; fill manually or rerun with corrected title/artist')
 print('set_lyrics',set_lyrics(pid,ly))
 total,m3u,ld,missp,missl,idx=export_all(a.playlist); print('tracks',total); print('m3u',m3u); print('lyrics_dir',ld); print('missing_paths',len(missp),missp); print('missing_lyrics',len(missl),missl); print('\n'.join(idx))
if __name__=='__main__': main()
