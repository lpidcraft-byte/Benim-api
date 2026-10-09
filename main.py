# main.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import random
import httpx

app = FastAPI(title="Sorgu API")

# CORS - GitHub Pages'ten çağrı için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- ANA SAYFA (HTML) ----------
HOME_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sorgu Merkezi</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: Arial, sans-serif; background:#1e1e2f; color:#eee; margin:0; padding:20px; }
  h1 { text-align:center; color:#61dafb; }
  .tabs { display:flex; justify-content:center; gap:10px; margin:20px 0; flex-wrap:wrap; }
  .tab-btn { padding:10px 20px; background:#2d2d44; color:#fff; border:none; border-radius:8px; cursor:pointer; }
  .tab-btn.active { background:#61dafb; color:#000; }
  .panel { display:none; max-width:600px; margin:0 auto; background:#2d2d44; padding:20px; border-radius:12px; }
  .panel.active { display:block; }
  input { width:100%; padding:10px; margin:8px 0; border-radius:6px; border:1px solid #444; background:#1e1e2f; color:#fff; }
  button.primary { width:100%; padding:12px; background:#61dafb; border:none; border-radius:8px; cursor:pointer; font-weight:bold; color:#000; }
  .result { margin-top:15px; padding:15px; background:#1e1e2f; border-radius:8px; line-height:1.6; }
  table { width:100%; border-collapse:collapse; margin-top:10px; font-size:14px; }
  td { padding:6px; border-bottom:1px solid #444; }
  td:first-child { color:#61dafb; font-weight:bold; }
</style>
</head>
<body>
<h1>🔍 Sorgu Merkezi</h1>

<div class="tabs">
  <button class="tab-btn active" onclick="showTab(0, this)">Ayak No</button>
  <button class="tab-btn" onclick="showTab(1, this)">Burç</button>
  <button class="tab-btn" onclick="showTab(2, this)">IP Sorgu</button>
</div>

<!-- AYAK -->
<div class="panel active">
  <h3>Ayak Numara Sorgu</h3>
  <input id="ad" placeholder="Adınız">
  <input id="soyad" placeholder="Soyadınız">
  <input id="yas" type="number" placeholder="Yaşınız">
  <button class="primary" onclick="ayakSorgu()">Sorgula</button>
  <div class="result" id="ayakRes"></div>
</div>

<!-- BURÇ -->
<div class="panel">
  <h3>Burç Sorgu</h3>
  <input id="dogum" type="date">
  <button class="primary" onclick="burcSorgu()">Burcumu Bul</button>
  <div class="result" id="burcRes"></div>
</div>

<!-- IP -->
<div class="panel">
  <h3>IP Adresi Sorgu</h3>
  <input id="ip" placeholder="Örn: 8.8.8.8">
  <button class="primary" onclick="ipSorgu()">Sorgula</button>
  <div class="result" id="ipRes"></div>
</div>

<script>
function showTab(i, btn){
  document.querySelectorAll('.panel').forEach((p,idx)=>p.classList.toggle('active', idx===i));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
}

async function ayakSorgu(){
  const ad=document.getElementById('ad').value;
  const soyad=document.getElementById('soyad').value;
  const yas=document.getElementById('yas').value;
  const r=await fetch('/api/ayak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ad,soyad,yas})});
  const d=await r.json();
  document.getElementById('ayakRes').innerHTML=`Ad: ${d.ad}<br>Soyad: ${d.soyad}<br>Yaş: ${d.yas}<br><b>Ayak Numarası: ${d.ayak_no}</b>`;
}

async function burcSorgu(){
  const tarih=document.getElementById('dogum').value;
  const r=await fetch('/api/burc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dogum_tarihi:tarih})});
  const d=await r.json();
  document.getElementById('burcRes').innerHTML=`<b>Burcunuz: ${d.burc}</b>`;
}

async function ipSorgu(){
  const ip=document.getElementById('ip').value;
  const r=await fetch('/api/ip?ip='+encodeURIComponent(ip));
  const d=await r.json();
  if(d.error){document.getElementById('ipRes').innerHTML='<span style="color:red">'+d.error+'</span>';return;}
  let html='<table>';
  for(const [k,v] of Object.entries(d)){
    if(k==='success')continue;
    html+=`<tr><td>${k}</td><td>${v}</td></tr>`;
  }
  html+='</table>';
  document.getElementById('ipRes').innerHTML=html;
}
</script>
</body>
</html>
"""

# ---------- MODELLER ----------
class AyakReq(BaseModel):
    ad: str
    soyad: str
    yas: int

class BurcReq(BaseModel):
    dogum_tarihi: str  # YYYY-MM-DD

# ---------- ROUTES ----------
@app.get("/", response_class=HTMLResponse)
def home():
    return HOME_HTML

@app.post("/api/ayak")
def ayak(req: AyakReq):
    ayak_no = random.randint(35, 43)
    return {
        "ad": req.ad,
        "soyad": req.soyad,
        "yas": req.yas,
        "ayak_no": ayak_no
    }

@app.post("/api/burc")
def burc(req: BurcReq):
    try:
        dt = datetime.strptime(req.dogum_tarihi, "%Y-%m-%d")
    except Exception:
        return {"error": "Geçersiz tarih formatı"}
    ay, gun = dt.month, dt.day

    if   (ay==3  and gun>=21) or (ay==4  and gun<=19): b="Koç"
    elif (ay==4  and gun>=20) or (ay==5  and gun<=20): b="Boğa"
    elif (ay==5  and gun>=21) or (ay==6  and gun<=20): b="İkizler"
    elif (ay==6  and gun>=21) or (ay==7  and gun<=22): b="Yengeç"
    elif (ay==7  and gun>=23) or (ay==8  and gun<=22): b="Aslan"
    elif (ay==8  and gun>=23) or (ay==9  and gun<=22): b="Başak"
    elif (ay==9  and gun>=23) or (ay==10 and gun<=22): b="Terazi"
    elif (ay==10 and gun>=23) or (ay==11 and gun<=21): b="Akrep"
    elif (ay==11 and gun>=22) or (ay==12 and gun<=21): b="Yay"
    elif (ay==12 and gun>=22) or (ay==1  and gun<=19): b="Oğlak"
    elif (ay==1  and gun>=20) or (ay==2  and gun<=18): b="Kova"
    else:                                              b="Balık"
    return {"burc": b, "tarih": req.dogum_tarihi}

@app.get("/api/ip")
async def ip_sorgu(ip: str):
    """ip-api.com üzerinden IP bilgisi çeker."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"http://ip-api.com/json/{ip}?lang=tr")
            data = r.json()
    except Exception as e:
        return {"error": f"Bağlantı hatası: {e}"}

    if data.get("status") != "success":
        return {"error": data.get("message", "IP bulunamadı")}

    return {
        "IP": data.get("query"),
        "Ülke": data.get("country"),
        "Ülke Kodu": data.get("countryCode"),
        "Bölge": data.get("regionName"),
        "Bölge Kodu": data.get("region"),
        "Şehir": data.get("city"),
        "Posta Kodu": data.get("zip"),
        "Enlem": data.get("lat"),
        "Boylam": data.get("lon"),
        "Zaman Dilimi": data.get("timezone"),
        "ISP": data.get("isp"),
        "Organizasyon": data.get("org"),
        "AS": data.get("as"),
        "Harita": f"https://www.google.com/maps?q={data.get('lat')},{data.get('lon')}"
    }

@app.get("/health")
def health():
    return {"status": "ok"}
