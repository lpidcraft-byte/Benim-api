from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def ana_sayfa():
    return {"mesaj": "Merhaba kanka, API'm çalışıyor!"}

@app.get("/link")
def link_ver():
    return {"link": "https://www.belimo.com", "durum": "aktif"}
