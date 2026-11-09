#!/usr/bin/env python3
"""
NSE Signal Scanner - web version (open it on your phone)
Setup once:  pip install yfinance
Run:         python nse_web.py
Then open the address it prints (like http://192.168.1.5:8765) on your phone,
while the phone is on the same Wi-Fi as this computer.
Data: Yahoo Finance, ~15 min delayed. Educational tool, not financial advice.
"""
import json, os, socket, sys
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    import yfinance as yf
except ImportError:
    sys.exit("Please run first:  pip install yfinance")

PORT = int(os.environ.get("PORT", 8765))
CACHE = {}


def resolve(q):
    q = q.strip()
    if q in CACHE:
        return CACHE[q]
    guess = q.upper().replace(" ", "") + ".NS"
    try:
        if not yf.Ticker(guess).history(period="5d").empty:
            CACHE[q] = (guess, q.upper()); return CACHE[q]
    except Exception:
        pass
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/search?newsCount=0&quotesCount=10&q=" + quote(q)
        data = json.loads(urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read())
        for r in data.get("quotes", []):
            if r.get("symbol", "").endswith(".NS") and r.get("quoteType") == "EQUITY":
                CACHE[q] = (r["symbol"], r.get("shortname") or r["symbol"]); return CACHE[q]
    except Exception:
        pass
    CACHE[q] = (None, None)
    return CACHE[q]


def analyse(a):
    q, mult, max_sp = a
    sym, name = resolve(q)
    if not sym:
        return {"q": q, "error": "No NSE match"}
    try:
        t = yf.Ticker(sym)
        h = t.history(period="3mo", interval="1d")
        h = h[h["Volume"] > 0] if not h.empty else h
        if len(h) < 6:
            return {"q": q, "name": name, "error": "Not enough data"}
        last, prev = h.iloc[-1], h.iloc[-2]
        vols = list(h["Volume"].iloc[-21:-1])
        avg = sum(vols) / len(vols)
        price, pclose, vol = float(last["Close"]), float(prev["Close"]), float(last["Volume"])
        chg = (price - pclose) / pclose * 100
        ratio = vol / avg if avg else None
        bid = ask = 0
        try:
            info = t.info
            bid, ask = info.get("bid") or 0, info.get("ask") or 0
        except Exception:
            pass
        spread = (ask - bid) / ((ask + bid) / 2) * 100 if bid > 0 and ask > 0 else None
        vol_ok = ratio is not None and ratio >= mult
        sp_ok = spread is None or spread <= max_sp
        vs = min(ratio / mult, 1.0) if ratio else 0.0
        ms = min(abs(chg) / 2.0, 1.0)
        strength = round(100 * (0.5 * vs + 0.4 * ms + 0.1 * (1.0 if sp_ok else 0.5))) if chg != 0 else 0
        if chg == 0:
            sig, cls, rank = ("Volume good, no direction" if vol_ok else "Neutral"), "N", 2
        elif vol_ok and sp_ok:
            sig, cls, rank = ("STRONG BULLISH", "SB", 0) if chg > 0 else ("STRONG BEARISH", "SR", 0)
        else:
            sig = ("Weak bullish" if chg > 0 else "Weak bearish") + (" (wide spread)" if vol_ok else " (low volume)")
            cls, rank = ("B" if chg > 0 else "R"), 1
        return {"q": q, "name": name, "sym": sym.replace(".NS", ""), "price": price, "chg": chg, "vol": vol,
                "avg": avg, "ratio": ratio, "spread": spread, "sig": sig, "cls": cls, "rank": rank,
                "date": str(h.index[-1].date()), "strength": strength}
    except Exception as e:
        return {"q": q, "name": name, "error": str(e)[:60]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype):
        b = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self.send(PAGE, "text/html")

    def do_POST(self):
        try:
            p = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            names = [n.strip() for n in p["names"] if n.strip()][:40]
            m, s = float(p.get("mult") or 1.5), float(p.get("sp") or 0.2)
            with ThreadPoolExecutor(max_workers=5) as ex:
                rows = list(ex.map(analyse, [(n, m, s) for n in names]))
            rows.sort(key=lambda r: (r.get("rank", 9), -(r.get("ratio") or 0)))
            self.send(json.dumps({"rows": rows}), "application/json")
        except Exception as e:
            self.send(json.dumps({"fatal": str(e)}), "application/json")


PAGE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>NSE Scanner</title>
<style>
:root{--bg:#f7f7f4;--card:#fff;--tx:#1b1d1f;--mu:#6b7076;--bd:#e2e2dc;--up:#15803d;--dn:#b91c1c;--ac:#0f766e;--upb:#dcfce7;--dnb:#fee2e2}
@media (prefers-color-scheme:dark){:root{--bg:#121415;--card:#1c1f21;--tx:#ecedee;--mu:#9aa0a6;--bd:#2c3033;--up:#4ade80;--dn:#f87171;--ac:#3cc4b4;--upb:#14351f;--dnb:#3d1b1b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,sans-serif}
main{max-width:640px;margin:0 auto;padding:14px}h1{font-size:21px;margin:4px 0 10px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:14px;margin-bottom:12px}
label{display:block;font-size:13px;color:var(--mu);margin:8px 0 4px}
input,textarea{font:inherit;color:var(--tx);background:var(--bg);border:1px solid var(--bd);border-radius:8px;padding:9px;width:100%}
.two{display:flex;gap:10px}.two>div{flex:1}
button{font:inherit;background:var(--ac);color:#fff;border:0;border-radius:10px;padding:12px;width:100%;font-weight:600;margin-top:12px}
.note{color:var(--mu);font-size:12.5px}.err{color:var(--dn)}
.row{padding:12px 0;border-top:1px solid var(--bd)}.row:first-child{border-top:0}
.top{display:flex;justify-content:space-between;gap:8px;align-items:center}
.sig{font-weight:700;border-radius:8px;padding:3px 8px;font-size:12.5px;white-space:nowrap}
.SB{background:var(--upb);color:var(--up)}.SR{background:var(--dnb);color:var(--dn)}.B{color:var(--up)}.R{color:var(--dn)}.N{color:var(--mu)}
.str{font-size:12.5px;font-weight:600;margin-top:3px}
.m{display:flex;flex-wrap:wrap;gap:2px 12px;font-size:12.5px;color:var(--mu);margin-top:4px}.up{color:var(--up)}.dn{color:var(--dn)}
</style></head><body><main>
<h1>NSE Signal Scanner</h1>
<div class="card">
<label>Company names (comma or new line)</label>
<textarea id="nm" rows="4" placeholder="Hyundai, Reliance, Tata Steel"></textarea>
<div class="two"><div><label>Volume multiple (x)</label><input id="mu" type="number" step="0.1" value="1.5"></div>
<div><label>Max spread %</label><input id="sp" type="number" step="0.01" value="0.2"></div></div>
<button id="go">Scan now</button>
<label style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="auto" style="width:auto"> Auto refresh every 60 seconds</label></div>
<div class="card"><div id="st" class="note">Results appear here.</div><div id="out"></div>
<p class="note">Strong signal = price direction + volume at or above the multiple + spread within the limit. Data from Yahoo, about 15 min delayed. Not financial advice.</p></div>
<script>
const $=id=>document.getElementById(id);let timer=null,busy=false;
try{$("nm").value=localStorage.getItem("nm")||"Hyundai, Reliance, Tata Steel, Infosys"}catch(e){}
const f=(x,d=2)=>x==null?"-":Number(x).toLocaleString("en-IN",{maximumFractionDigits:d});
async function scan(){
 if(busy)return;busy=true;$("st").textContent="Scanning... (first scan can take a few seconds)";
 const names=$("nm").value.split(/[\n,]+/).map(s=>s.trim()).filter(Boolean);
 try{localStorage.setItem("nm",$("nm").value)}catch(e){}
 try{
  const r=await(await fetch("/api/scan",{method:"POST",body:JSON.stringify({names,mult:$("mu").value,sp:$("sp").value})})).json();
  if(r.fatal){$("st").innerHTML='<span class="err">'+r.fatal+'</span>';busy=false;return}
  const d=(r.rows.find(x=>x.date)||{}).date;
  $("st").textContent="Updated "+new Date().toLocaleTimeString()+(d?". Latest session in data: "+d:"");
  $("out").innerHTML=r.rows.map(x=>x.error?`<div class="row"><b>${x.q}</b> <span class="N">${x.error}</span></div>`:
  `<div class="row"><div class="top"><span><b>${x.sym}</b> <span class="note">${x.name}</span></span><span style="text-align:right"><span class="sig ${x.cls}">${x.sig}</span><div class="str ${x.chg>=0?"up":"dn"}">${x.chg==0?"Neutral":x.strength+"% "+(x.chg>0?"bullish":"bearish")}</div></span></div>
  <div class="m"><span>₹${f(x.price)} <span class="${x.chg>=0?"up":"dn"}">${(x.chg>=0?"+":"")+f(x.chg)}%</span></span><span>Vol ${f(x.vol,0)}</span><span>20d avg ${f(x.avg,0)}</span><span><b>${f(x.ratio)}x</b></span><span>Spread ${x.spread==null?"n/a":f(x.spread,3)+"%"}</span></div></div>`).join("");
 }catch(e){$("st").innerHTML='<span class="err">Cannot reach the PC. Is the script still running and are you on the same Wi-Fi?</span>'}
 busy=false;
}
$("go").onclick=scan;
$("auto").onchange=e=>{clearInterval(timer);if(e.target.checked){scan();timer=setInterval(scan,60000)}};
</script></main></body></html>"""


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "YOUR-PC-IP"


if __name__ == "__main__":
    print("\nNSE Scanner is running.")
    print("On this PC open:     http://localhost:%d" % PORT)
    print("On your phone open:  http://%s:%d   (same Wi-Fi)" % (lan_ip(), PORT))
    print("\nKeep this window open. Press Ctrl+C to stop.\n")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
