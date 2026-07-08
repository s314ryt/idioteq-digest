#!/usr/bin/env python3
"""
IDIOTEQ Feed Digest — pobiera wszystkie feedy (Feedly OPML + extra_feeds.txt),
wysyla mailem w stylu Feedly tylko NOWE wpisy (stan w seen.json => nic nie ginie).
Wysylka: SMTP Gmail (App Password). Zero nowych wpisow = brak maila.
Env: MAIL_USER, MAIL_PASS, MAIL_TO
"""
import os, sys, json, html, re, socket, smtplib, ssl, time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlparse
import urllib.request
import feedparser

socket.setdefaulttimeout(20)
HERE = os.path.dirname(os.path.abspath(__file__))
SEEN_PATH = os.path.join(HERE, "seen.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
MAX_SEEN = 40000          # ile ID trzymamy (auto-prune)
IMG_FALLBACK_LIMIT = 120  # ile og:image dociagnac na run (tylko dla wysylanych)

def load_feeds():
    feeds = []
    root = ET.parse(os.path.join(HERE, "feeds.opml")).getroot().find("body")
    for cat in root.findall("outline"):
        if cat.get("xmlUrl"):
            feeds.append(("Inne", cat.get("title") or "", cat.get("xmlUrl"))); continue
        cname = cat.get("title") or cat.get("text") or "Inne"
        for f in cat.findall("outline"):
            if f.get("xmlUrl"):
                feeds.append((cname, f.get("title") or "", f.get("xmlUrl")))
    extra = os.path.join(HERE, "extra_feeds.txt")
    if os.path.exists(extra):
        for line in open(extra, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"): continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 3:
                feeds.append((parts[0], parts[1], parts[2]))
    # dedupe po URL
    seen=set(); out=[]
    for c,t,u in feeds:
        if u in seen: continue
        seen.add(u); out.append((c,t,u))
    return out

def entry_id(e):
    return e.get("id") or e.get("link") or (e.get("title","")+e.get("published",""))

def img_from(e):
    for k in ("media_thumbnail","media_content"):
        v=e.get(k)
        if v and v[0].get("url"): return v[0]["url"]
    for l in e.get("links",[]):
        if l.get("rel")=="enclosure" and "image" in (l.get("type") or ""): return l.get("href")
    blob=e.get("summary","")+((e.get("content",[{}])[0].get("value","")) if e.get("content") else "")
    m=re.search(r'<img[^>]+src="([^"]+)"',blob)
    return m.group(1) if m else ""

def clean(t,n=220):
    t=re.sub("<[^>]+>","",t or ""); t=html.unescape(t).strip(); t=re.sub(r"\s+"," ",t)
    return (t[:n]+"…") if len(t)>n else t

def fetch(feed):
    cname,ftitle,url=feed; out=[]
    for attempt in range(2):
        try:
            d=feedparser.parse(url, request_headers=UA)
            src=d.feed.get("title") or ftitle or urlparse(url).netloc.replace("www.","")
            for e in d.entries[:30]:
                dt=None
                if e.get("published_parsed"): dt=datetime(*e.published_parsed[:6],tzinfo=timezone.utc)
                elif e.get("updated_parsed"): dt=datetime(*e.updated_parsed[:6],tzinfo=timezone.utc)
                out.append({"id":entry_id(e),"cat":cname,"src":src,
                    "title":clean(e.get("title",""),160),"link":e.get("link",""),
                    "summary":clean(e.get("summary","")),"img":img_from(e),"dt":dt})
            return out, ("ok" if out else "empty"), (ftitle or url)
        except Exception:
            time.sleep(1)
    return out, "fail", (ftitle or url)

def og_image(url):
    try:
        req=urllib.request.Request(url,headers=UA)
        h=urllib.request.urlopen(req,timeout=12).read(200000).decode("utf-8","ignore")
        m=re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',h) or \
          re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',h)
        return m.group(1) if m else ""
    except Exception:
        return ""

def ago(dt):
    if dt is None: return ""
    s=(datetime.now(timezone.utc)-dt).total_seconds()
    if s<0: return "teraz"
    if s<60: return "teraz"
    if s<3600: return f"{int(s//60)}min"
    if s<86400: return f"{int(s//3600)}h"
    return f"{int(s//86400)}d"

def render(items, stats):
    now=datetime.now(timezone.utc); rows=[]
    for it in items:
        if it["img"]:
            thumb=f'<img src="{html.escape(it["img"])}" width="76" height="76" style="width:76px;height:76px;object-fit:cover;border-radius:6px;display:block;background:#eee" alt="">'
        else:
            thumb='<div style="width:76px;height:76px;border-radius:6px;background:#f0f0f0"></div>'
        meta=f'{html.escape(it["src"])}'
        if ago(it["dt"]): meta+=f' &nbsp;/&nbsp; {ago(it["dt"])}'
        raw=it["summary"]; sm=html.escape((raw[:150]+"…") if len(raw)>150 else raw)
        rows.append(f'<tr><td style="padding:11px 0;border-bottom:1px solid #ececec"><table cellpadding="0" cellspacing="0" width="100%"><tr><td width="76" valign="top" style="padding-right:12px">{thumb}</td><td valign="top"><a href="{html.escape(it["link"])}" style="color:#111;text-decoration:none;font-size:15px;font-weight:600;line-height:1.25">{html.escape(it["title"])}</a><div style="color:#8a8a8a;font-size:11px;margin:3px 0 4px">{meta} <span style="color:#c9c9c9">&middot; {html.escape(it["cat"])}</span></div><div style="color:#6b6b6b;font-size:12px;line-height:1.4">{sm}</div></td></tr></table></td></tr>')
    body="".join(rows)
    return f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body style="margin:0;padding:0;background:#f6f6f6"><table cellpadding="0" cellspacing="0" width="100%" style="background:#f6f6f6"><tr><td align="center" style="padding:12px 6px"><table cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;background:#fff;border-radius:12px;padding:16px 16px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif"><tr><td style="padding-bottom:4px"><span style="font-size:18px;font-weight:700;color:#111">IDIOTEQ &middot; Feed digest</span><div style="color:#8a8a8a;font-size:11px;margin-top:3px">{len(items)} nowych &middot; {now.strftime("%Y-%m-%d %H:%M UTC")}</div></td></tr><tr><td><table cellpadding="0" cellspacing="0" width="100%">{body}</table></td></tr><tr><td style="padding-top:12px;border-top:2px solid #ececec;color:#9a9a9a;font-size:11px;line-height:1.6"><b style="color:#6b6b6b">Sanity check</b> &nbsp;&middot;&nbsp; źródła: {stats["ok"]}/{stats["total"]} odpowiedziało &nbsp;&middot;&nbsp; {stats["empty"]} pustych/martwych &nbsp;&middot;&nbsp; {stats["fail"]} błędów<br>pobrano {stats["items"]} wpisów &nbsp;&middot;&nbsp; {len(items)} nowych &middot; zrzut {now.strftime("%Y-%m-%d %H:%M UTC")}</td></tr></table></td></tr></table></body></html>'

def send_mail(subject, html_body):
    user=os.environ["MAIL_USER"]; pw=os.environ["MAIL_PASS"]; to=os.environ.get("MAIL_TO",user)
    msg=MIMEMultipart("alternative")
    msg["Subject"]=subject; msg["From"]=user; msg["To"]=to
    msg.attach(MIMEText("Wersja HTML. Wlacz obrazy, aby zobaczyc digest.","plain"))
    msg.attach(MIMEText(html_body,"html"))
    ctx=ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ctx) as s:
        s.login(user,pw); s.sendmail(user,[to],msg.as_string())

def main():
    feeds=load_feeds()
    print(f"Feedów: {len(feeds)}", flush=True)
    items=[]; stats={"total":len(feeds),"ok":0,"empty":0,"fail":0,"dead":[]}
    with ThreadPoolExecutor(max_workers=32) as ex:
        futs=[ex.submit(fetch,f) for f in feeds]
        for fut in as_completed(futs):
            res,status,name=fut.result()
            items+=res
            stats[status]=stats.get(status,0)+1
            if status!="ok": stats["dead"].append(f"{name} [{status}]")
    # dedupe po id/link w ramach runu
    uniq={}
    for it in items:
        k=it["id"] or it["link"]
        if k and k not in uniq: uniq[k]=it
    items=list(uniq.values())
    stats["items"]=len(items)
    print(f"Źródła OK:{stats['ok']} puste:{stats['empty']} błędy:{stats['fail']} / {stats['total']}", flush=True)

    seen = json.load(open(SEEN_PATH)) if os.path.exists(SEEN_PATH) else None
    first_run = seen is None
    seen_set = set(seen or [])

    new=[it for it in items if (it["id"] or it["link"]) not in seen_set]
    print(f"Wpisów pobranych: {len(items)} | nowych: {len(new)} | first_run={first_run}", flush=True)

    # aktualizuj stan ZAWSZE (nawet first run) — prune do MAX_SEEN
    all_ids=[it["id"] or it["link"] for it in items if (it["id"] or it["link"])]
    merged=list(seen_set)+[i for i in all_ids if i not in seen_set]
    merged=merged[-MAX_SEEN:]
    json.dump(merged, open(SEEN_PATH,"w"))

    if first_run:
        print("Pierwszy run — seeduje stan, nie wysylam (uniknac zalewu).", flush=True)
        return
    if not new:
        print("Brak nowych — nie wysylam.", flush=True); return

    # sortuj: najnowsze na gorze (brak daty => na dol)
    new.sort(key=lambda x:(x["dt"] or datetime(1970,1,1,tzinfo=timezone.utc)), reverse=True)
    # og:image fallback dla wysylanych bez grafiki
    need=[it for it in new if not it["img"]][:IMG_FALLBACK_LIMIT]
    if need:
        with ThreadPoolExecutor(max_workers=16) as ex:
            res=list(ex.map(lambda it:(it,og_image(it["link"])), need))
        for it,img in res:
            if img: it["img"]=img
    subject=f"IDIOTEQ digest — {len(new)} nowych"
    if os.environ.get("MAIL_DRY"):
        open(os.path.join(HERE,"dry_preview.html"),"w").write(render(new, stats)); print("DRY: zapisano dry_preview.html"); return
    send_mail(subject, render(new, stats))
    print(f"Wyslano {len(new)} wpisow.", flush=True)

if __name__=="__main__":
    main()
