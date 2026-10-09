import telebot
from telebot import types
import json
import random
import time
import threading
import os
import string
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, Request
import uvicorn


# ============================================================
# ⚙️ GENEL YAPILANDIRMA (CONFIG)
# ============================================================

BOT_TOKEN = "8935278587:AAFfwr3wg73ln55fIiBmgWxLiDhhvUn1xvw"

# 👑 OWNER ID (Ana Admin - Silinemez)
OWNER_ID = 8913966694 

# 🔴 YÖNETİCİLERİN ID LİSTESİ ve SEVİYELERİ
ADMIN_LEVELS = {
    "8913966694": "owner",
}

ADMIN_IDS = [8913966694]

STATUS_CHANNELS = [
    -1003941046835  # Logs kanalı
]

REQUIRED_CHANNELS = [
    {
        "id": -1003947388912,
        "link": "https://t.me/vantoriumbanned",
        "name": "VANTORİUM BANNED"
    },
    {
        "id": -1003731592787,
        "link": "https://t.me/kurdishgroup1",
        "name": "Kurdistan #bilindbûn"
    }
]

pending_captcha = {}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
DB_FILE = "sms_panel_v7.json"

user_msg_times = {}


# ============================================================
# 📦 VARSAYILAN ÜRÜNLER (BOŞ - ADMIN EKLEYECEK)
# ============================================================
default_products = {}


# ============================================================
# 💾 VERİTABANI MOTORU (LOAD DATABASE)
# ============================================================
def load_database():
    if not os.path.exists(DB_FILE):
        default = {
            "users": {}, "groups": {},
            "stats": {"total_spent": 0, "total_orders": 0, "start_date": str(datetime.now())},
            "logs": [], "gift_codes": {}, "bot_status": "active",
            "products": default_products,
            "categories": {
                "genel": {"name": " Genel Ürünler", "emoji_id": "6129402906782207599", "color": "primary"}
            }
        }
        with open(DB_FILE, "w", encoding="utf-8") as f: 
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default

    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        if "gift_codes" not in data: data["gift_codes"] = {} 
        if "bot_status" not in data: data["bot_status"] = "active"
        if "groups" not in data: data["groups"] = {}
        if "products" not in data: data["products"] = default_products
        
        if "categories" not in data or not data["categories"]: 
            data["categories"] = {
                "genel": {"name": " Genel Ürünler", "emoji_id": "6129402906782207599", "color": "primary"}
            }
        else:
            eklenecekler = {}
            for k_id, k_verisi in eklenecekler.items():
                if k_id not in data["categories"]:
                    data["categories"][k_id] = k_verisi

        for cid, cdata in list(data["categories"].items()):
            if isinstance(cdata, str):
                data["categories"][cid] = {
                    "name": cdata,
                    "emoji_id": "6129402906782207599",
                    "color": "primary"
                }
                
        for gid, gdata in list(data["groups"].items()):
            if isinstance(gdata, str): 
                data["groups"][gid] = {"title": gdata, "lang": "tr", "warnings": {}}
        return data
        

db = load_database()

def save_database(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def check_user_exists(uid, ref_id=None):
    uid = str(uid)
    
    if uid in db["users"]:
        if "language" not in db["users"][uid]: db["users"][uid]["language"] = None
        if "is_banned" not in db["users"][uid]: db["users"][uid]["is_banned"] = False
        if "order_history" not in db["users"][uid]: db["users"][uid]["order_history"] = []
        if "is_vip" not in db["users"][uid]: db["users"][uid]["is_vip"] = db["users"][uid].get("is_premium", False)
        if "daily_bonus_count" not in db["users"][uid]: db["users"][uid]["daily_bonus_count"] = 0
        if "last_bonus_date" not in db["users"][uid]: db["users"][uid]["last_bonus_date"] = ""
        return
        
    db["users"][uid] = {
        "balance": 0, 
        "is_banned": False,
        "refs": 0, 
        "orders_count": 0, 
        "order_history": [],
        "orders": {},
        "last_bonus_time": 0,
        "daily_bonus_count": 0,
        "last_bonus_date": "",
        "is_vip": False,
        "reg_date": str(datetime.now()), 
        "language": None,
        "status": "pending"
    }
    
    if ref_id and str(ref_id) != uid:
        db["users"][uid]["pending_ref"] = str(ref_id)
        
    save_database(db)
    
def award_referral(uid, ref_id):
    uid = str(uid); ref_id = str(ref_id)
    if ref_id in db["users"] and ref_id != uid:
        is_vip = db["users"][ref_id].get("is_vip", False)
        bonus = 2 if is_vip else 1
        db["users"][ref_id]["balance"] += bonus
        db["users"][ref_id]["refs"] += 1
        save_database(db)
        vip_txt = " <b>(VIP Bonus: +2 Puan!)</b>" if is_vip else ""
        try: bot.send_message(int(ref_id), f"<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> <b>Tebrikler!</b> Davet linkinizle yeni bir üye katıldı, <b>+{bonus} Puan</b> kazandınız!{vip_txt}")
        except: pass

def is_member_of_channels(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
        
    if not REQUIRED_CHANNELS: 
        return True
        
    for ch in REQUIRED_CHANNELS:
        try:
            status = bot.get_chat_member(ch["id"], user_id).status
            if status in ["left", "kicked"]: 
                return False
        except Exception as e:
            print(f"Kanal kontrol hatası ({ch.get('name')}): {e}")
            return False
    return True

def get_channel_join_keyboard():
    markup = InlineKeyboardMarkup()
    
    for ch in REQUIRED_CHANNELS:
        if "button" in ch:
            markup.row(ch["button"])
        else:
            markup.row(
                pbtn(ch["name"], emoji_id="5188481279963715781", url=ch["link"], style="success")
            )
            
    markup.row(
        pbtn(" Katıldım, Kontrol Et", "check_channels", emoji_id="6325541629260206557", style="success")
    )
    
    return markup
    

def send_math_captcha(chat_id, uid, ref_id=None):
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    op = random.choice(["+", "-"])
    operators = {"+": lambda x, y: x + y, "-": lambda x, y: x - y}
    answer = operators[op](a, b)
    
    wrong = set()
    while len(wrong) < 3:
        yanlis = answer + random.choice([-5,-4,-3,-2,-1,1,2,3,4,5])
        if yanlis != answer:
            wrong.add(yanlis)
    
    secenekler = [answer] + list(wrong)
    random.shuffle(secenekler)
    
    pending_captcha[str(uid)] = {
        "answer": answer,
        "ref": str(ref_id) if ref_id else None,
        "time": time.time()
    }
    
    emoji_ids = ["5895410404141568046", "5895410404141568046", "5895410404141568046", "5895410404141568046"]
    random.shuffle(emoji_ids)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for i, s in enumerate(secenekler):
        btn = types.InlineKeyboardButton(
            text=str(s),
            callback_data=f"captcha_{uid}_{s}_{answer}",
            icon_custom_emoji_id=emoji_ids[i % len(emoji_ids)]
        )
        markup.add(btn)
    
    bot.send_message(
        chat_id,
        f"<b><tg-emoji emoji-id=\"5030732809128379408\">🗓</tg-emoji> Güvenlik Doğrulaması</b> <tg-emoji emoji-id=\"5030732809128379408\">🗓</tg-emoji>\n\n"
        f"<tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji> Soruyu çözün <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji>\n\n"
        f"<b>{a} {op} {b} = ?</b>\n\n"
        f"<i><tg-emoji emoji-id=\"5780834596673296534\">➕</tg-emoji> Doğru cevabı seçin: <tg-emoji emoji-id=\"5780834596673296534\">➕</tg-emoji></i>",
        reply_markup=markup
    )

def verify_captcha_step(m, uid):
    pass

def get_admin_level(uid):
    return ADMIN_LEVELS.get(str(uid), None)

def is_owner(uid):
    return get_admin_level(uid) == "owner"

def is_super_admin(uid):
    level = get_admin_level(uid)
    return level in ["owner", "super_admin"]

def is_admin(uid):
    return get_admin_level(uid) is not None

def notify_admins_with_markup(text, markup):
    for admin in ADMIN_IDS:
        try: bot.send_message(admin, text, reply_markup=markup)
        except: pass

def notify_everyone(status_msg):
    for ch_id in STATUS_CHANNELS:
        try: 
            bot.send_message(ch_id, status_msg)
            time.sleep(0.5) 
        except: pass
    for user_id in db.get("users", {}):
        try: 
            bot.send_message(int(user_id), status_msg)
            time.sleep(0.1) 
        except: pass
        

def create_colored_button(text: str, callback_data: str = None, color: str = "primary", url: str = None):
    style_map = {
        "blue": "primary",
        "green": "success",
        "red": "danger",
        "primary": "primary",
        "success": "success",
        "danger": "danger",
    }

    button_style = style_map.get(color)

    kwargs = {}
    if callback_data:
        kwargs["callback_data"] = callback_data
    if url:
        kwargs["url"] = url

    try:
        if button_style:
            return InlineKeyboardButton(text, style=button_style, **kwargs)
    except TypeError:
        pass

    return InlineKeyboardButton(text, **kwargs)

# ============================================================
# 🎬 HAREKETLİ ANİMASYON FONKSİYONLARI (PREMIUM GÖRÜNÜM)
# ============================================================
def animated_loading(chat_id, final_text, markup=None):
    msg = bot.send_message(chat_id, "<tg-emoji emoji-id=\"6235771761892270039\">🔼</tg-emoji> <i>Sistem başlatılıyor...</i>")
    frames = [
        "<tg-emoji emoji-id=\"5981091707456851997\">⏳</tg-emoji> <b>Güvenli bağlantı kuruluyor...</b>\n[▰▱▱▱▱▱▱▱▱▱] 10%",
        "<tg-emoji emoji-id=\"5818775306974006843\">🌐</tg-emoji> <b>Şifreli tünel açılıyor...</b>\n[▰▰▰▰▱▱▱▱▱▱] 40%",
        "<tg-emoji emoji-id=\"6235482220966977551\">🙂</tg-emoji> <b>VIP Sunucuya bağlanılıyor...</b>\n[▰▰▰▰▰▰▰▱▱▱] 70%",
        "<tg-emoji emoji-id=\"6237621131860253190\">✅</tg-emoji> <b>İşlem tamamlanıyor...</b>\n[▰▰▰▰▰▰▰▰▰▰] 100%"
    ]
    for frame in frames:
        time.sleep(0.7) 
        try: bot.edit_message_text(frame, chat_id, msg.message_id)
        except: pass
    time.sleep(0.5)
    try: bot.edit_message_text(final_text, chat_id, msg.message_id, reply_markup=markup)
    except: pass


# ============================================================
# 🔌 GLOBAL PREMIUM BUTON FONKSİYONU
# ============================================================
def pbtn(text, callback_data=None, emoji_id=None, url=None, style=None):
    if url:
        btn = types.InlineKeyboardButton(text=text, url=url)
    else:
        btn = types.InlineKeyboardButton(text=text, callback_data=callback_data)
    
    try:
        if style:
            btn.style = style
    except:
        pass
        
    try:
        if emoji_id:
            btn.icon_custom_emoji_id = emoji_id
    except:
        pass
        
    return btn


# ============================================================
# 📱 KULLANICI ANA MENÜSÜ (MAIN KEYBOARD)
# ============================================================
def get_main_keyboard(uid):
    try:
        lang = db["users"][str(uid)].get("language", "tr")
        user_balance = db["users"][str(uid)]["balance"]
    except:
        lang = "tr"
        user_balance = 0

    current_hour = datetime.now().hour
    if 6 <= current_hour < 19:
        greet_tr, greet_en = "<tg-emoji emoji-id=\"5402477260982731644\">☀️</tg-emoji> Günaydın", "<tg-emoji emoji-id=\"5402477260982731644\">☀️</tg-emoji> Good morning"
    else:
        greet_tr, greet_en = "<tg-emoji emoji-id=\"5402477260982731644\">☀️</tg-emoji> İyi geceler", "<tg-emoji emoji-id=\"5897561886404120587\">🌛</tg-emoji> Good night"
    
    all_texts = {
        "tr": {
            "profile": " Profilim", "referral": " Davet Et Kazan",
            "leaderboard": " Lider Top 10", "otp_group": " Gurup", "otp_admin": " Admin ",
            "redeem": " Promosyon Kodu", "lang": " Dil Değiştir", "support": " 7/24 Destek",
            "shopping": " Normal Mağaza", "vip_shopping": " VIP Mağaza",
            "orders": " Sipariş Geçmişi",
            "help": " Yardım", "products_list": " Ürün Listesi",
            "admin_panel": " YÖNETİM MERKEZİ",
            "welcome": f"{greet_tr}!\n <b>Dijital Alışveriş Merkezine Hoşgeldiniz!</b>\nLütfen yapmak istediğiniz işlemi seçiniz:",
            "refund_btn": " Bakiye İadesi", "balance_btn": " Bakiye: {} Puan",
            "buy_vip": " VIP Satın Al (20 Referans)",
            "transfer": " Puan Transfer"
        },
        "en": {
            "profile": " My Profile", "referral": " Invite & Earn",
            "leaderboard": " Top 10 Leaders", "otp_group": " Group", "otp_admin": " Admin ",
            "redeem": " Promo Code", "lang": " Language", "support": " 24/7 Support",
            "shopping": " Normal Store", "vip_shopping": " VIP Store",
            "orders": " Order History",
            "help": " Help", "products_list": " Product List",
            "admin_panel": " ADMIN CENTER",
            "welcome": f"{greet_en}!\n <b>Welcome to Digital Hub!</b>\nPlease select an operation:",
            "refund_btn": " Refund Request", "balance_btn": " Balance: {} Pts",
            "buy_vip": " Buy VIP (20 Referrals)",
            "transfer": " Transfer Points"
        }
    }
    
    texts = all_texts.get(lang, all_texts["tr"])
    markup = types.InlineKeyboardMarkup()
    
    markup.row(
        pbtn(texts["profile"], callback_data="nav_profile", emoji_id="4967667085606912536", style="success")
    )
    
    markup.row(
        pbtn(" Günlük Bonus Al", callback_data="nav_daily_bonus", emoji_id="5251562950698759162", style="success")
    )
    
    markup.row(
        pbtn(texts["shopping"], callback_data="nav_shopping", emoji_id="5143290574673019778", style="primary"),
        pbtn(texts["vip_shopping"], callback_data="nav_vip_shopping", emoji_id="6005862519019673214", style="danger")
    )

    is_vip = db["users"].get(str(uid), {}).get("is_vip", False)
    if not is_vip:
        markup.row(
            pbtn(texts["buy_vip"], callback_data="nav_buy_vip", emoji_id="6005862519019673214", style="success")
        )
    
    markup.row(
        pbtn(texts["orders"], callback_data="nav_orders", emoji_id="5909003528956812070", style="primary"), 
        pbtn(texts["redeem"], callback_data="nav_redeem", emoji_id="5418010521309815154", style="danger")
    )
    
    markup.row(
        pbtn(texts["referral"], callback_data="nav_referral", emoji_id="5253510310345600737", style="success"),
        pbtn(texts["help"], callback_data="nav_help", emoji_id="5373251851074415873", style="primary")
    )

    markup.row(
        pbtn(texts.get("transfer", " Puan Transferi"), callback_data="nav_transfer", emoji_id="6325541629260206557", style="primary")
    )
    
    markup.row(
        pbtn(texts["otp_admin"], emoji_id="5332769714135394894", url="tg://openmessage?user_id=8913966694")
    )
    
    markup.row(
        pbtn(texts["lang"], callback_data="nav_lang", emoji_id="6147492389909961118", style="primary")
    )
    
    if int(uid) in ADMIN_IDS:
        markup.row(
            pbtn(texts["admin_panel"], callback_data="adm_dashboard", emoji_id="5818813162815753343", style="success")
        )
        
    markup.row(
        pbtn(texts["refund_btn"], callback_data="nav_refund", emoji_id="5352759161945867747", style="danger")
    )
    
    markup.row(
        pbtn(texts["balance_btn"].format(user_balance), callback_data="nav_profile", emoji_id="5215420556089776398", style="primary")
    )
    
    return markup, texts
    

# ==========================================
# 👑 YÖNETİCİ PANELİ MENÜSÜ (ADMIN KEYBOARD)
# ==========================================
def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup()
    
    markup.row(
        pbtn(" Aktif Siparişler", callback_data="adm_active_orders", emoji_id="5271801931814165886")
    )
    
    markup.row(
        pbtn(" Kullanıcı Banla", callback_data="adm_ban_user", emoji_id="5271801931814165886"),
        pbtn(" Ban Kaldır", callback_data="adm_unban_user", emoji_id="5271801931814165886")
    )
    
    markup.row(
        pbtn(" Ürün Ekle", callback_data="adm_add_product", emoji_id="5780834596673296534", style="success"),
        pbtn(" Ürün Sil", callback_data="adm_del_product", emoji_id="5314504236132747481", style="danger")
    )
    markup.row(
        pbtn(" Toplu Ürün Sil", callback_data="adm_del_all_products", emoji_id="5314504236132747481", style="danger")
    )

    markup.row(
        pbtn(" Kategori Ekle", callback_data="adm_add_category", emoji_id="5780834596673296534", style="success"),
        pbtn(" Kategori Sil", callback_data="adm_del_category", emoji_id="5314504236132747481", style="danger")
    )

    markup.row(
        pbtn(" VIP Ürün Ekle", callback_data="adm_add_vip_product", emoji_id="6005862519019673214", style="success"),
        pbtn(" VIP Ürün Sil", callback_data="adm_del_vip_product", emoji_id="5314504236132747481", style="danger")
    )

    markup.row(
        pbtn(" VIP Kategori Ekle", callback_data="adm_add_vip_category", emoji_id="6005862519019673214", style="success"),
        pbtn(" VIP Kategori Sil", callback_data="adm_del_vip_category", emoji_id="5314504236132747481", style="danger")
    )
    
    markup.row(
        pbtn(" VIP Ver", callback_data="adm_give_prem", emoji_id="6005862519019673214", style="success"),
        pbtn(" VIP Kaldır", callback_data="adm_take_prem", emoji_id="5314504236132747481", style="danger")
    )
    
    markup.row(
        pbtn(" Puan Tanımla (Ekle)", callback_data="adm_add_balance", emoji_id="5271801931814165886"),
        pbtn(" Puan Sil", callback_data="adm_sub_balance", emoji_id="5314504236132747481")
    )
    
    markup.row(
        pbtn(" Herkese Toplu Duyuru", callback_data="adm_broadcast", emoji_id="5271801931814165886"),
        pbtn(" Bottan Özel Mesaj", callback_data="adm_send_msg", emoji_id="5271801931814165886")
    )
    
    markup.row(
        pbtn(" Kupon Kodu Oluştur", callback_data="adm_create_gift", emoji_id="5271801931814165886"),
        pbtn(" Tüm Kullanıcıları Listele", callback_data="adm_list_users", emoji_id="5271801931814165886")
    )
    
    markup.row(
        pbtn(" Analiz Raporu", callback_data="adm_stats", emoji_id="5271801931814165886"),
        pbtn(" Sistem Durumu", callback_data="adm_bot_status", emoji_id="5271801931814165886")
    )
    
    markup.row(
        pbtn(" Admin Ekle", callback_data="adm_add_admin", emoji_id="5271801931814165886"),
        pbtn(" Admin Sil", callback_data="adm_del_admin", emoji_id="5271801931814165886")
    )
    
    markup.row(
        pbtn(" Admin Listesi", callback_data="adm_list_admins", emoji_id="5271801931814165886")
    )
    
    markup.row(
        pbtn(" Çıkış", callback_data="nav_main", emoji_id="5271801931814165886")
    )
    
    return markup


# ==========================================
# 🌐 DİL SEÇİM MENÜSÜ (LANGUAGE KEYBOARD)
# ==========================================
def get_language_keyboard():
    markup = types.InlineKeyboardMarkup()
    
    markup.row(
        pbtn(" Türkçe", callback_data="lang_tr", emoji_id="5985763094276611276"),
        pbtn(" English", callback_data="lang_en", emoji_id="5956225444540847358")
    )
    markup.row(
        pbtn(" Ana Merkeze Dön", callback_data="nav_main", emoji_id="5253997076169115797")
    )
    
    return markup
    

# ============================================================
# 🕹️ CALLBACK HANDLER (ANA MOTOR & ADMIN SISTEMLERI)
# ============================================================

@bot.callback_query_handler(func=lambda call: True)
def process_callbacks(call):
    uid = str(call.from_user.id)
    chat_id = call.message.chat.id
    
    if call.message.chat.type != 'private': 
        return
        
    check_user_exists(uid)

    if db.get("bot_status", "active") != "active" and int(uid) not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "🛠️ Sistem Bakımda/Kapalı!", show_alert=True)
        return

    if db["users"].get(uid, {}).get("is_banned") and int(uid) not in ADMIN_IDS: 
        bot.answer_callback_query(call.id, "⚠️ Erişiminiz engellenmiştir!", show_alert=True)
        return

    if call.data == "check_channels":
        import time
        time.sleep(0.5)
        
        try:
            üye = is_member_of_channels(call.from_user.id)
        except Exception as e:
            bot.answer_callback_query(call.id, f"⚠️ Kontrol hatası: {e}", show_alert=True)
            return
            
        if üye:
            db["users"][uid]["status"] = "active"
            
            ref_id = db["users"].get(uid, {}).get("pending_ref")
            if not ref_id and "pending_ref" in db:
                ref_id = db["pending_ref"].get(uid) or db["pending_ref"].get(int(uid))

            if ref_id:
                award_referral(uid, ref_id)
                
                if "pending_ref" in db["users"].get(uid, {}):
                    db["users"][uid].pop("pending_ref", None)
                if "pending_ref" in db and uid in db["pending_ref"]:
                    db["pending_ref"].pop(uid, None)
                if "pending_ref" in db and int(uid) in db["pending_ref"]:
                    db["pending_ref"].pop(int(uid), None)
                    
            save_database(db)
                
            kb, txts = get_main_keyboard(uid)
            try:
                bot.edit_message_text(f"<tg-emoji emoji-id=\"6237621131860253190\">✅</tg-emoji> <b>Doğrulama Başarılı!</b>\n\n{txts['welcome']}", chat_id, call.message.message_id, reply_markup=kb)
            except:
                bot.send_message(chat_id, f"<tg-emoji emoji-id=\"6237621131860253190\">✅</tg-emoji> <b>Doğrulama Başarılı!</b>\n\n{txts['welcome']}", reply_markup=kb)
        else:
            bot.answer_callback_query(call.id, "⚠️ Henüz kanalların hepsine katılmadın ya da sistem üyeliğini algılayamadı!", show_alert=True)
        return
        

    if call.data.startswith("captcha_"):
        parts = call.data.split("_")
        cap_uid = parts[1]
        secilen = int(parts[2])
        dogru = int(parts[3])
        
        if cap_uid != uid:
            bot.answer_callback_query(call.id, "⚠️ Bu soru size ait değil!", show_alert=True)
            return
        
        if cap_uid not in pending_captcha:
            bot.answer_callback_query(call.id, "⚠️ Oturum süresi doldu, /start yaz.", show_alert=True)
            return
        
        ref_id = pending_captcha[cap_uid].get("ref")
        
        if secilen == dogru:
            del pending_captcha[cap_uid]
            bot.answer_callback_query(call.id, "✅ Doğru!", show_alert=False)
            try: bot.delete_message(chat_id, call.message.message_id)
            except: pass
            
            if REQUIRED_CHANNELS and not is_member_of_channels(call.from_user.id):
                db["users"][uid]["pending_ref"] = ref_id
                save_database(db)
                bot.send_message(chat_id, "<tg-emoji emoji-id=\"5780405967527089720\">📢</tg-emoji> <b>Bota erişmek için kanallara katılman gerekiyor! <tg-emoji emoji-id=\"5780405967527089720\">📢</tg-emoji></b>", reply_markup=get_channel_join_keyboard())
                return
            
            if ref_id:
                award_referral(uid, ref_id)
            kb, txts = get_main_keyboard(uid)
            bot.send_message(chat_id, f"<tg-emoji emoji-id=\"6287474217424263219\">🎉</tg-emoji> <b>Doğrulama Başarılı! <tg-emoji emoji-id=\"6287474217424263219\">🎉</tg-emoji></b>\n\n{txts['welcome']}", reply_markup=kb)
        else:
            bot.answer_callback_query(call.id, "❌ Yanlış! Tekrar dene.", show_alert=True)
            try: bot.delete_message(chat_id, call.message.message_id)
            except: pass
            send_math_captcha(chat_id, uid, ref_id)
        return
    if call.data == "nav_main":
        kb, txts = get_main_keyboard(uid)
        try:
            bot.edit_message_text(txts['welcome'], chat_id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(chat_id, txts['welcome'], reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if call.data == "nav_profile":
        u = db["users"][uid]
        is_vip = u.get("is_vip", False)
        vip_badge = " '<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>' <b>VIP</b>" if is_vip else ""
        txt = (f"<tg-emoji emoji-id=\"5348136664738839786\">👤</tg-emoji> <b>Profil Özeti</b>{vip_badge}\n\n"
               f"<tg-emoji emoji-id=\"5974526806995242353\">🆔</tg-emoji> <b>Kullanıcı ID:</b> <code>{uid}</code>\n"
               f"<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> <b>Cüzdan Bakiyesi:</b> {u['balance']} Puan\n"
               f"<tg-emoji emoji-id=\"6034834452843074121\">🤝</tg-emoji> <b>Davet Edilen:</b> {u['refs']} Kişi\n"
               f"<tg-emoji emoji-id=\"5348227245599105972\">💼</tg-emoji> <b>Toplam Sipariş:</b> {u['orders_count']}\n"
               f"<tg-emoji emoji-id=\"5028418466000930064\">📆</tg-emoji> <b>Kayıt Tarihi:</b> {u['reg_date'][:16]}\n\n"
               f"{'<tg-emoji emoji-id=\"6005862519019673214\">👑</tg-emoji> <b>VIP Avantajları:</b> Günde 2x Bonus | +2 Davet Puanı | VIP Mağaza' if is_vip else '💡 VIP olarak: 2x Günlük Bonus, +2 Davet Puanı, VIP Mağazaya erişim!'}")
        
        markup = InlineKeyboardMarkup()
        markup.row(pbtn(" Günlük Bonus Al", "nav_daily_bonus", emoji_id="5251562950698759162", style="success"))
        markup.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
        
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=markup)
        except:
            bot.send_message(chat_id, txt, reply_markup=markup)
        bot.answer_callback_query(call.id)
        return

    if call.data == "nav_daily_bonus":
        u = db["users"][uid]
        is_vip = u.get("is_vip", False)
        today = datetime.now().strftime("%Y-%m-%d")
        last_date = u.get("last_bonus_date", "")
        daily_count = u.get("daily_bonus_count", 0) if last_date == today else 0
        max_claims = 2 if is_vip else 1

        if last_date == today and daily_count >= max_claims:
            remaining = "Yarın tekrar gel!"
            bot.answer_callback_query(call.id, f"⏳ Bugünkü bonus hakkını kullandın! {remaining}", show_alert=True)
            return

        db["users"][uid]["balance"] += 1
        if last_date != today:
            db["users"][uid]["daily_bonus_count"] = 1
            db["users"][uid]["last_bonus_date"] = today
        else:
            db["users"][uid]["daily_bonus_count"] = daily_count + 1
        save_database(db)

        new_bal = db["users"][uid]["balance"]
        kalan = max_claims - db["users"][uid]["daily_bonus_count"]
        extra = f"\n'<tg-emoji emoji-id=\"6120660741369369103\">👍</tg-emoji>' Bugün için <b>{kalan} hakkın</b> daha var!" if kalan > 0 else "\n'<tg-emoji emoji-id=\"6120660741369369103\">👍</tg-emoji>' Bugünkü tüm bonus haklarını kullandın!"
        vip_note = " <b>(VIP Avantajı: Günde 2x!)</b>" if is_vip else ""

        txt = (f" <b>Günlük Bonus Alındı!{vip_note}</b>\n\n"
               f"<tg-emoji emoji-id=\"5780834596673296534\">➕</tg-emoji> <b>+1 Puan</b> hesabınıza eklendi!\n"
               f"<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> <b>Yeni Bakiye:</b> {new_bal} Puan{extra}")

        markup = InlineKeyboardMarkup()
        if kalan > 0:
            markup.row(pbtn(" Tekrar Al", "nav_daily_bonus", emoji_id="5251562950698759162", style="success"))
        markup.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))

        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=markup)
        except:
            bot.send_message(chat_id, txt, reply_markup=markup)
        bot.answer_callback_query(call.id)
        return

    if call.data == "nav_orders":
        orders = db["users"][uid].get("orders", {})
        if not orders:
            txt = "<tg-emoji emoji-id=\"5909003528956812070\">📦</tg-emoji> <b>Sipariş Geçmişiniz</b>\n\nHenüz hiç siparişiniz bulunmuyor."
            kb = InlineKeyboardMarkup()
            kb.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
            try:
                bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb)
            except:
                bot.send_message(chat_id, txt, reply_markup=kb)
        else:
            kb = InlineKeyboardMarkup()
            durum_emoji_id = {
                "alindi":  "5415803109983133508",
                "islemde": "5415896658665808854",
                "teslim":  "5415722549281561774",
                "iptal":   "5463260230861202209"
            }
            durum_stil = {
                "alindi": "primary", "islemde": "primary",
                "teslim": "success", "iptal": "danger"
            }
            for oid, odata in list(orders.items())[-10:]:
                d = odata.get("durum", "alindi")
                ad = odata.get("urun", "Ürün")
                kb.row(pbtn(
                    f"#{oid} — {ad}",
                    f"order_detail_{oid}",
                    emoji_id=durum_emoji_id.get(d, "5778479949572738874"),
                    style=durum_stil.get(d, "primary")
                ))
            kb.row(pbtn("Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
            txt = "<tg-emoji emoji-id=\"5909003528956812070\">📦</tg-emoji> <b>Siparişleriniz</b>\n\nBir siparişe tıklayarak durumunu görebilirsiniz."
            try:
                bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb)
            except:
                bot.send_message(chat_id, txt, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("order_detail_"):
        oid = call.data.replace("order_detail_", "")
        orders = db["users"][uid].get("orders", {})
        if oid not in orders:
            bot.answer_callback_query(call.id, "⚠️ Sipariş bulunamadı!", show_alert=True)
            return
        o = orders[oid]
        durum_emoji = {"alindi": "<tg-emoji emoji-id=\"6035130900075777681\">🚪</tg-emoji>", "islemde": "<tg-emoji emoji-id=\"5981091707456851997\">⏳</tg-emoji>", "teslim": "<tg-emoji emoji-id=\"5462919317832082236\">⏳</tg-emoji>", "iptal": "<tg-emoji emoji-id=\"5463260230861202209\">🚪</tg-emoji>"}
        durum_yazi = {"alindi": "Sipariş Alındı", "islemde": "İşleme Alındı", "teslim": "Teslim Edildi", "iptal": "İptal Edildi"}
        d = o.get("durum", "alindi")
        txt = (f"<tg-emoji emoji-id=\"5909003528956812070\">📦</tg-emoji> <b>Sipariş Detayı</b>\n\n"
               f"<tg-emoji emoji-id=\"4967853603151676186\">🔖</tg-emoji> <b>Sipariş ID:</b> <code>#{oid}</code>\n"
               f"<tg-emoji emoji-id=\"4970023558068568720\">🛍️</tg-emoji> <b>Ürün:</b> {o.get('urun', '-')}\n"
               f"<tg-emoji emoji-id=\"5891105528356018797\">💎</tg-emoji> <b>Ödenen:</b> {o.get('fiyat', 0)} Puan\n"
               f"<tg-emoji emoji-id=\"5030732809128379408\">🗓</tg-emoji> <b>Tarih:</b> {o.get('tarih', '-')}\n\n"
               f"<b>Durum İzleme:</b>\n"
               f"{'<tg-emoji emoji-id=\"6041720006973067267\">👍</tg-emoji>' if d in ['alindi','islemde','teslim'] else '<tg-emoji emoji-id=\"5778479949572738874\">↔️</tg-emoji>'} Sipariş Alındı\n"
               f"{'<tg-emoji emoji-id=\"6041720006973067267\">👍</tg-emoji>' if d in ['islemde','teslim'] else '<tg-emoji emoji-id=\"5778479949572738874\">↔️</tg-emoji>'} İşleme Alındı\n"
               f"{'<tg-emoji emoji-id=\"6041720006973067267\">👍</tg-emoji>' if d == 'teslim' else '<tg-emoji emoji-id=\"5778479949572738874\">↔️</tg-emoji>'} Teslim Edildi\n"
               f"\n<b>Güncel Durum:</b> {durum_emoji.get(d,'🟡')} <b>{durum_yazi.get(d,'Alındı')}</b>")
        if d == "iptal":
            txt += f"\n\n'<tg-emoji emoji-id=\"6120660741369369103\">👍</tg-emoji>' <i>Bu sipariş iptal edildi, puan iade edildi.</i>"
        if o.get("not"):
            txt += f"\n\n📝 <b>Not:</b> <code>{o['not']}</code>"
        kb = InlineKeyboardMarkup()
        kb.row(pbtn("Siparişlere Dön", "nav_orders", emoji_id="5253997076169115797", style="primary"))
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(chat_id, txt, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return

    if call.data == "nav_shopping":
        categories = db.get("categories", {"genel": "Genel"})
        m = InlineKeyboardMarkup()
        cat_list = list(categories.items())
        for i in range(0, len(cat_list), 2):
            row_buttons = []
            cat_key1, cat_data1 = cat_list[i]
            cat_name1 = cat_data1["name"] if isinstance(cat_data1, dict) else cat_data1
            row_buttons.append(pbtn(cat_name1, f"ncat_{cat_key1}", emoji_id="6205984948218762570", style="success"))
            if i + 1 < len(cat_list):
                cat_key2, cat_data2 = cat_list[i+1]
                cat_name2 = cat_data2["name"] if isinstance(cat_data2, dict) else cat_data2
                row_buttons.append(pbtn(cat_name2, f"ncat_{cat_key2}", emoji_id="5780834596673296534", style="success"))
            m.row(*row_buttons)
        m.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
        try:
            bot.edit_message_text("🛍️ <b>Normal Mağazaya Hoşgeldiniz!</b>\n\nBir kategori seçin:", chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, "🛍️ <b>Normal Mağazaya Hoşgeldiniz!</b>\n\nBir kategori seçin:", reply_markup=m)
        bot.answer_callback_query(call.id)
        return

    if call.data == "nav_vip_shopping":
        is_vip = db["users"].get(uid, {}).get("is_vip", False)
        if not is_vip:
            bot.answer_callback_query(call.id,
                "👑 Lütfen önce VIP olun!\nVIP mağazaya erişmek için VIP üyeliğiniz gerekiyor.",
                show_alert=True)
            return
        categories = db.get("vip_categories", db.get("categories", {"genel": "Genel"}))
        m = InlineKeyboardMarkup()
        cat_list = list(categories.items())
        for i in range(0, len(cat_list), 2):
            row_buttons = []
            cat_key1, cat_data1 = cat_list[i]
            cat_name1 = cat_data1["name"] if isinstance(cat_data1, dict) else cat_data1
            row_buttons.append(pbtn(cat_name1, f"vcat_{cat_key1}", emoji_id="6005862519019673214", style="danger"))
            if i + 1 < len(cat_list):
                cat_key2, cat_data2 = cat_list[i+1]
                cat_name2 = cat_data2["name"] if isinstance(cat_data2, dict) else cat_data2
                row_buttons.append(pbtn(cat_name2, f"vcat_{cat_key2}", emoji_id="6005862519019673214", style="danger"))
            m.row(*row_buttons)
        m.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
        try:
            bot.edit_message_text("👑 <b>VIP Mağazaya Hoşgeldiniz!</b>\n\nÖzel VIP ürünler sizi bekliyor! Bir kategori seçin:", chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, "👑 <b>VIP Mağazaya Hoşgeldiniz!</b>\n\nÖzel VIP ürünler sizi bekliyor! Bir kategori seçin:", reply_markup=m)
        bot.answer_callback_query(call.id)
        return

    if call.data == "nav_buy_vip":
        u = db["users"].get(uid, {})
        is_vip = u.get("is_vip", False)
        if is_vip:
            bot.answer_callback_query(call.id, "✅ Zaten VIP üyesiniz!", show_alert=True)
            return
        refs = u.get("refs", 0)
        VIP_REF_REQUIRED = 20
        kalan = VIP_REF_REQUIRED - refs
        m = InlineKeyboardMarkup()
        if refs >= VIP_REF_REQUIRED:
            m.row(pbtn(" VIP'i Aktif Et!", "nav_activate_vip", emoji_id="6005862519019673214", style="success"))
        m.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
        if refs >= VIP_REF_REQUIRED:
            txt = ("👑 <b>Tebrikler! VIP için yeterli referansınız var!</b>\n\n"
                   f"'<tg-emoji emoji-id=\"5231200819986047254\">👍</tg-emoji>' Referans sayınız: <b>{refs}/{VIP_REF_REQUIRED}</b>\n\n"
                   "Aşağıdaki butona basarak VIP'i aktif edebilirsiniz!")
        else:
            txt = ("'<tg-emoji emoji-id=\"6267068789146260253\">👍</tg-emoji>' <b>VIP Satın Al</b>\n\n"
                   f"VIP olmak için <b>{VIP_REF_REQUIRED} referans</b> şart!\n\n"
                   f"'<tg-emoji emoji-id=\"5231200819986047254\">👍</tg-emoji>' Mevcut referansınız: <b>{refs}/{VIP_REF_REQUIRED}</b>\n"
                   f"'<tg-emoji emoji-id=\"6120660741369369103\">👍</tg-emoji>' Eksik referans: <b>{kalan} kişi daha davet edin!</b>\n\n"
                   "• '<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' <b>VIP Avantajları:</b>\n"
                   "• '<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' VIP Mağazaya erişim\n"
                   "• '<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' Günde <b>2 kez</b> günlük bonus\n"
                   "• '<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' Her davette <b>+2 Puan</b>")
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, txt, reply_markup=m)
        bot.answer_callback_query(call.id)
        return

    if call.data == "nav_activate_vip":
        u = db["users"].get(uid, {})
        refs = u.get("refs", 0)
        VIP_REF_REQUIRED = 20
        if refs < VIP_REF_REQUIRED:
            bot.answer_callback_query(call.id, f"❌ Yeterli referansın yok! ({refs}/{VIP_REF_REQUIRED})", show_alert=True)
            return
        if u.get("is_vip", False):
            bot.answer_callback_query(call.id, "✅ Zaten VIP üyesiniz!", show_alert=True)
            return
        db["users"][uid]["is_vip"] = True
        db["users"][uid]["is_premium"] = True
        save_database(db)
        m = InlineKeyboardMarkup()
        m.row(pbtn(" VIP Mağazaya Git", "nav_vip_shopping", emoji_id="6266995104687330978", style="success"))
        m.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
        txt = ("'<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>' <b>VIP üyeliğiniz aktif edildi! Tebrikler!</b>\n\n"
               "'<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' <b>Kazandığınız Avantajlar:</b>\n"
               "• '<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>' VIP Mağazaya erişim açıldı\n"
               "• '<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' Günde <b>2 kez</b> günlük bonus\n"
               "• '<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' Her davette <b>+2 Puan</b>\n\n"
               "<i>İyi kullanmalar! '<tg-emoji emoji-id=\"6289727022260294842\">👍</tg-emoji>'</i>")
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, txt, reply_markup=m)
        for admin_id in ADMIN_IDS:
            try: bot.send_message(admin_id, f"'<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>' <b>Yeni VIP Üye!</b>\nKullanıcı ID: <code>{uid}</code>\nReferans: {refs}")
            except: pass
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("ncat_"):
        cat_key = call.data.split("_", 1)[1]
        products = db.get("products", {})
        m = InlineKeyboardMarkup()
        has_product = False
        for p_key, p_val in products.items():
            if p_val.get("category") == cat_key and not p_val.get("vip_only", False):
                has_product = True
                stock = p_val.get("stock", 0)
                prod_emoji = p_val.get("emoji_id", "5373251851074415873")
                if stock > 0:
                    m.row(pbtn(f"{p_val['name']} | {p_val['price']} Puan", f"prod_{cat_key}_{p_key}", emoji_id=prod_emoji, style="success"))
                else:
                    m.row(pbtn(f"{p_val['name']} (Tükenmiş)", "stock_empty", emoji_id="5314504236132747481", style="danger"))
        m.row(pbtn(" Kategorilere Dön", "nav_shopping", emoji_id="5253997076169115797", style="danger"))
        txt = "'<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>' <b>Ürünler Listeleniyor</b>\n\nSatın almak istediğiniz ürünü seçin:" if has_product else "⚠️ <b>Bu kategoride ürün bulunamadı!</b>"
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, txt, reply_markup=m)
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("vcat_"):
        is_vip = db["users"].get(uid, {}).get("is_vip", False)
        if not is_vip:
            bot.answer_callback_query(call.id, "👑 Lütfen önce VIP olun!", show_alert=True)
            return
        cat_key = call.data.split("_", 1)[1]
        products = db.get("vip_products", db.get("products", {}))
        m = InlineKeyboardMarkup()
        has_product = False
        for p_key, p_val in products.items():
            if p_val.get("category") == cat_key:
                has_product = True
                stock = p_val.get("stock", 0)
                prod_emoji = p_val.get("emoji_id", "6005862519019673214")
                if stock > 0:
                    m.row(pbtn(f"👑 {p_val['name']} | {p_val['price']} Puan", f"vprod_{cat_key}_{p_key}", emoji_id=prod_emoji, style="danger"))
                else:
                    m.row(pbtn(f"{p_val['name']} (Tükenmiş)", "stock_empty", emoji_id="5314504236132747481", style="danger"))
        m.row(pbtn(" VIP Kategorilere Dön", "nav_vip_shopping", emoji_id="5253997076169115797", style="danger"))
        txt = "'<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>' <b>VIP Ürünler Listeleniyor</b>\n\nSatın almak istediğiniz ürünü seçin:" if has_product else "⚠️ <b>Bu VIP kategorisinde henüz ürün yok!</b>"
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, txt, reply_markup=m)
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("cat_"):
        cat_key = call.data.split("_", 1)[1]
        products = db.get("products", {})
        m = InlineKeyboardMarkup()
        has_product = False
        for p_key, p_val in products.items():
            if p_val.get("category") == cat_key:
                has_product = True
                stock = p_val.get("stock", 0)
                prod_emoji = p_val.get("emoji_id", "5373251851074415873")
                if stock > 0:
                    m.row(pbtn(f"{p_val['name']} | {p_val['price']} Puan", f"prod_{cat_key}_{p_key}", emoji_id=prod_emoji, style="success"))
                else:
                    m.row(pbtn(f"{p_val['name']} (Tükenmiş)", "stock_empty", emoji_id="5314504236132747481", style="danger"))
        m.row(pbtn(" Kategorilere Dön", "nav_shopping", emoji_id="5253997076169115797", style="danger"))
        txt = "📝 <b>Ürünler Listeleniyor</b>\n\nSatın almak istediğiniz ürünü seçin:" if has_product else "⚠️ <b>Bu kategoride ürün bulunamadı!</b>"
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, txt, reply_markup=m)
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("prod_"):
        parts = call.data.split("_", 2)
        cat_key = parts[1]
        p_key = parts[2]
        
        product = db.get("products", {}).get(p_key)
        if not product:
            bot.answer_callback_query(call.id, "⚠️ Ürün bulunamadı!", show_alert=True)
            return
            
        prod_emoji = product.get("emoji_id", "5373251851074415873")
        prod_color = product.get("color", "success")
        stock = product.get("stock", 0)
        
        txt = (f"<b>{product['name']}</b>\n\n"
               f"<tg-emoji emoji-id=\"5152608171214243098\">💵</tg-emoji> <b>Fiyat:</b> {product['price']} Puan\n"
               f"<tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> <b>Stok:</b> {stock} Adet\n\n"
               f"<i><tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji> Satın almak istiyorsunuz <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji></i>")
        
        m = InlineKeyboardMarkup()
        m.row(
            pbtn("Evet", f"confirm_buy_{p_key}_{cat_key}", emoji_id="5348514879558926674", style="success"),
            pbtn("Hayır", f"cat_{cat_key}", emoji_id="5350572310627632617", style="danger")
        )
        
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, txt, reply_markup=m)
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("confirm_buy_"):
        parts = call.data.split("_", 3)
        p_key = parts[2]
        cat_key = parts[3] if len(parts) > 3 else "genel"
        
        product = db.get("products", {}).get(p_key)
        if not product:
            bot.send_message(chat_id, "⚠️ Ürün bulunamadı!")
            return
        
        stock = product.get("stock", 99)
        if stock <= 0:
            bot.answer_callback_query(call.id, "🔴 Ürün tükenmiş!", show_alert=True)
            return
        
        cost = product["price"]
        item_name = product["name"]
        item = p_key
        
        if db["users"][uid]["balance"] < cost:
            bot.send_message(chat_id, f"<tg-emoji emoji-id=\"5348514879558926674\">👎</tg-emoji> <b>Yetersiz Bakiye!</b>\n{cost} puana ihtiyacınız var.")
            return
        
        order_id = "".join(random.choices(string.digits, k=6))
        date_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        db["users"][uid]["balance"] -= cost
        db["users"][uid]["orders_count"] += 1
        db["products"][item]["stock"] = max(0, stock - 1)
        
        db["users"][uid].setdefault("orders", {})[order_id] = {
            "urun": item_name,
            "fiyat": cost,
            "tarih": date_str,
            "durum": "alindi",
            "urun_key": item
        }
        db["users"][uid].setdefault("order_history", []).insert(0, f"[{date_str}] #{order_id} {item_name} (-{cost}<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji>)")
        save_database(db)
        
        buyer_name = call.from_user.first_name or "Bilinmeyen"
        buyer_uname = f" (@{call.from_user.username})" if call.from_user.username else ""
        final_msg = (f"<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> <b>Siparişiniz Alındı!</b>\n\n"
                     f"<tg-emoji emoji-id=\"6287264550005773857\">🔖</tg-emoji> <b>Sipariş ID:</b> <code>#{order_id}</code>\n"
                     f"<tg-emoji emoji-id=\"5348227245599105972\">💼</tg-emoji> <b>Ürün:</b> {item_name}\n"
                     f"<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> <b>Ödenen:</b> {cost} Puan\n\n"
                     f"<tg-emoji emoji-id=\"5251684060186569219\">🔔</tg-emoji> <b>Önemli:</b> Siparişinizin işleme alınabilmesi için\n"
                     f"lütfen <b>sipariş bağlantınızı / profilinizi</b> aşağıya gönderin.\n\n"
                     f"<i>Örn: https://t.me/kullaniciadiniz</i>")

        threading.Thread(target=animated_loading, args=(chat_id, final_msg)).start()
        def wait_for_order_link(chat_id_=chat_id, uid_=uid, order_id_=order_id, item_name_=item_name,
                                cost_=cost, buyer_name_=buyer_name, buyer_uname_=buyer_uname):
            def _step(m2):
                link = m2.text.strip() if m2.text else "(gönderilmedi)"
                if link.lower() == "/iptal":
                    bot.send_message(chat_id_, "<tg-emoji emoji-id=\"6221914376329237010\">⚠️</tg-emoji> İptal edildi.")
                    return
                if uid_ in db["users"] and order_id_ in db["users"][uid_].get("orders", {}):
                    db["users"][uid_]["orders"][order_id_]["link"] = link
                    save_database(db)
                bot.send_message(chat_id_,
                    f"<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> <b>Link alındı!</b>\n"
                    f"<tg-emoji emoji-id=\"6287264550005773857\">🔖</tg-emoji> Sipariş ID: <code>#{order_id_}</code>\n"
                    f"<tg-emoji emoji-id=\"5981091707456851997\">⏳</tg-emoji> Siparişiniz en kısa sürede işleme alınacak."
                )
                adm_markup = InlineKeyboardMarkup()
                adm_markup.add(
                    InlineKeyboardButton(f"<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> TESLİM ET (#{order_id_})", callback_data=f"o_app_{uid_}_{item}_{order_id_}"),
                    InlineKeyboardButton(f"<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> İPTAL (#{order_id_})", callback_data=f"o_rej_{uid_}_{item}_{order_id_}")
                )
                adm_markup.add(InlineKeyboardButton(f"<tg-emoji emoji-id=\"5956229471585441542\">🔵</tg-emoji> İŞLEME AL", callback_data=f"o_proc_{uid_}_{order_id_}"))
                notify_admins_with_markup(
                    f"<tg-emoji emoji-id=\"5348227245599105972\">💼</tg-emoji> <b>YENİ SİPARİŞ!</b>\n\n"
                    f"<tg-emoji emoji-id=\"6287264550005773857\">🔖</tg-emoji> Sipariş ID: <code>#{order_id_}</code>\n"
                    f"<tg-emoji emoji-id=\"6032994772321309200\">👤</tg-emoji> Kullanıcı: {buyer_name_}{buyer_uname_}\n"
                    f"<tg-emoji emoji-id=\"6325655265504923619\">🆔</tg-emoji> ID: <code>{uid_}</code>\n"
                    f"<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> Ürün: <b>{item_name_}</b>\n"
                    f"<tg-emoji emoji-id=\"6267068789146260253\">💰</tg-emoji> Fiyat: {cost_} Puan\n"
                    f"<tg-emoji emoji-id=\"5780406047416174369\">🔗</tg-emoji> <b>Kullanıcı Linki:</b> {link}", adm_markup
                )
            import time as _time
            _time.sleep(4)
            try:
                bot.register_next_step_handler_by_chat_id(chat_id_, _step)
            except:
                pass
        threading.Thread(target=wait_for_order_link).start()
        
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(f"✅ TESLİM ET (#{order_id})", callback_data=f"o_app_{uid}_{item}_{order_id}"), 
            InlineKeyboardButton(f"❌ İPTAL (#{order_id})", callback_data=f"o_rej_{uid}_{item}_{order_id}")
        )
        markup.add(InlineKeyboardButton("🔵 İŞLEME AL", callback_data=f"o_proc_{uid}_{order_id}"))
        notify_admins_with_markup(
            f"<tg-emoji emoji-id=\"5348227245599105972\">💼</tg-emoji> <b>YENİ SİPARİŞ!</b>\n\n"
            f"<tg-emoji emoji-id=\"6287264550005773857\">🔖</tg-emoji> Sipariş ID: <code>#{order_id}</code>\n"
            f"<tg-emoji emoji-id=\"6032994772321309200\">👤</tg-emoji> Kullanıcı: {buyer_name}{buyer_uname}\n"
            f"<tg-emoji emoji-id=\"6325655265504923619\">🆔</tg-emoji> ID: <code>{uid}</code>\n"
            f"<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> Ürün: <b>{item_name}</b>\n"
            f"<tg-emoji emoji-id=\"6267068789146260253\">💰</tg-emoji> Fiyat: {cost} Puan", markup
        )
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("vprod_"):
        is_vip = db["users"].get(uid, {}).get("is_vip", False)
        if not is_vip:
            bot.answer_callback_query(call.id, "👑 Lütfen önce VIP olun!", show_alert=True)
            return
        parts = call.data.split("_", 2)
        cat_key = parts[1]
        p_key = parts[2]
        vip_products = db.get("vip_products", db.get("products", {}))
        product = vip_products.get(p_key)
        if not product:
            bot.answer_callback_query(call.id, "⚠️ VIP ürün bulunamadı!", show_alert=True)
            return
        stock = product.get("stock", 0)
        txt = (f"'<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>' <b>{product['name']}</b>\n\n"
               f"'<tg-emoji emoji-id=\"6267068789146260253\">👍</tg-emoji>' <b>Fiyat:</b> {product['price']} Puan\n"
               f"'<tg-emoji emoji-id=\"5242391348685859513\">👍</tg-emoji>' <b>Stok:</b> {stock} Adet\n\n"
               f"<i>Bu VIP özel bir üründür. Satın almak istiyor musunuz?</i>")
        m = InlineKeyboardMarkup()
        m.row(
            pbtn(" Evet", f"vconfirm_{cat_key}_{p_key}", emoji_id="5348514879558926674", style="success"),
            pbtn(" Hayır", f"vcat_{cat_key}", emoji_id="5823260889213575047", style="danger")
        )
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m)
        except:
            bot.send_message(chat_id, txt, reply_markup=m)
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("vconfirm_"):
        is_vip = db["users"].get(uid, {}).get("is_vip", False)
        if not is_vip:
            bot.answer_callback_query(call.id, "👑 Lütfen önce VIP olun!", show_alert=True)
            return
        parts = call.data.split("_", 2)
        cat_key = parts[1]
        p_key = parts[2]
        vip_products = db.get("vip_products", db.get("products", {}))
        product = vip_products.get(p_key)
        if not product:
            bot.answer_callback_query(call.id, "⚠️ Ürün bulunamadı!", show_alert=True)
            return
        stock = product.get("stock", 0)
        if stock <= 0:
            bot.answer_callback_query(call.id, "🔴 Ürün tükenmiş!", show_alert=True)
            return
        cost = product["price"]
        item_name = product["name"]
        if db["users"][uid]["balance"] < cost:
            bot.send_message(chat_id, f"👑 <b>Yetersiz Bakiye!</b>\n{cost} puana ihtiyacınız var, bakiyeniz: {db['users'][uid]['balance']} Puan")
            return
        order_id = "".join(random.choices(string.digits, k=6))
        date_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        db["users"][uid]["balance"] -= cost
        db["users"][uid]["orders_count"] += 1
        if "vip_products" in db:
            db["vip_products"][p_key]["stock"] = max(0, stock - 1)
        db["users"][uid].setdefault("orders", {})[order_id] = {
            "urun": item_name, "fiyat": cost, "tarih": date_str,
            "durum": "alindi", "urun_key": p_key, "vip_order": True
        }
        db["users"][uid].setdefault("order_history", []).insert(0, f"[{date_str}] #{order_id} '<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>'{item_name} (-{cost}'<tg-emoji emoji-id=\"6325717349257187998\">👍</tg-emoji>')")
        save_database(db)
        buyer_name = call.from_user.first_name or "Bilinmeyen"
        buyer_uname = f" (@{call.from_user.username})" if call.from_user.username else ""
        final_msg = (f"'<tg-emoji emoji-id=\"6120635817674149717\">👍</tg-emoji>' <b>VIP Siparişiniz Alındı!</b>\n\n"
                     f"'<tg-emoji emoji-id=\"6287264550005773857\">👍</tg-emoji>' <b>Sipariş ID:</b> <code>#{order_id}</code>\n"
                     f"'<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>' <b>Ürün:</b> {item_name}\n"
                     f"'<tg-emoji emoji-id=\"6325717349257187998\">👍</tg-emoji>' <b>Ödenen:</b> {cost} Puan\n\n"
                     f"<i>Siparişiniz işleme alınıyor.</i>")
        threading.Thread(target=animated_loading, args=(chat_id, final_msg)).start()
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(f" TESLİM ET (#{order_id})", callback_data=f"o_app_{uid}_{p_key}_{order_id}"),
            InlineKeyboardButton(f" İPTAL (#{order_id})", callback_data=f"o_rej_{uid}_{p_key}_{order_id}")
        )
        markup.add(InlineKeyboardButton(" İŞLEME AL", callback_data=f"o_proc_{uid}_{order_id}"))
        notify_admins_with_markup(
            f"👑 <b>YENİ VIP SİPARİŞ!</b>\n\n"
            f"🔖 Sipariş ID: <code>#{order_id}</code>\n"
            f"👤 Kullanıcı: {buyer_name}{buyer_uname}\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"👑 Ürün: <b>{item_name}</b>\n"
            f"💰 Fiyat: {cost} Puan", markup
        )
        bot.answer_callback_query(call.id)
        return

    if call.data == "stock_empty":
        bot.answer_callback_query(call.id, "🔴 Bu ürün tükenmiş!", show_alert=True)
        return

    if call.data.startswith("buy_shop_"):
        bot.answer_callback_query(call.id, "ℹ️ Lütfen Evet/Hayır seçeneğini kullanın.", show_alert=True)
        return

    if call.data.startswith("o_proc_"):
        if int(uid) not in ADMIN_IDS: return
        parts = call.data.split("_", 3)
        target_uid = parts[2]
        order_id = parts[3]
        if target_uid in db["users"] and order_id in db["users"][target_uid].get("orders", {}):
            db["users"][target_uid]["orders"][order_id]["durum"] = "islemde"
            save_database(db)
        try:
            bot.edit_message_text(call.message.text + f"\n\n<tg-emoji emoji-id=\"5415896658665808854\">🔵</tg-emoji> <b>Durum: İŞLEME ALINDI</b>", chat_id, call.message.message_id)
        except: pass
        try: bot.send_message(int(target_uid), f"<tg-emoji emoji-id=\"5415896658665808854\">🔵</tg-emoji> <b>Siparişiniz İşleme Alındı!</b>\n<tg-emoji emoji-id=\"6287264550005773857\">🔖</tg-emoji> Sipariş ID: <code>#{order_id}</code>\n\n<i>En kısa sürede teslim edilecektir.</i>")
        except: pass
        bot.answer_callback_query(call.id, "<tg-emoji emoji-id=\"5780834596673296534\">➕</tg-emoji> İşleme alındı", show_alert=True)
        return

    if call.data.startswith("o_app_"):
        if int(uid) not in ADMIN_IDS: return
        parts = call.data.split("_", 4)
        target_uid = parts[2]
        item = parts[3]
        order_id = parts[4] if len(parts) > 4 else "?"
        product = db.get("products", {}).get(item)
        item_name = product["name"] if product else item
        admin_name = call.from_user.first_name or "Yönetim"
        
        msg = bot.send_message(chat_id, f"📦 <b>#{order_id}</b> — <b>{item_name}</b> teslim ediliyor.\nMüşteriye gönderilecek bilgiyi yazın:\n<i>(İptal için /iptal)</i>")
        original_text = call.message.text
        bot.register_next_step_handler(msg, lambda m: admin_deliver_order_step(m, target_uid, item_name, call.message.message_id, chat_id, admin_name, original_text, order_id))
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("o_rej_"):
        if int(uid) not in ADMIN_IDS: return
        parts = call.data.split("_", 4)
        target_uid = parts[2]
        item = parts[3]
        order_id = parts[4] if len(parts) > 4 else "?"
        product = db.get("products", {}).get(item)
        cost = product["price"] if product else 0
        item_name = product["name"] if product else item
        admin_name = call.from_user.first_name or "Yönetim"
        
        if target_uid in db["users"]:
            db["users"][target_uid]["balance"] += cost
            if order_id in db["users"][target_uid].get("orders", {}):
                db["users"][target_uid]["orders"][order_id]["durum"] = "iptal"
            save_database(db)
            
        try:
            bot.edit_message_text(call.message.text + f"\n\n<tg-emoji emoji-id=\"5463260230861202209\">🟥</tg-emoji> <b>Durum: {admin_name} Tarafından İPTAL EDİLDİ</b>", chat_id, call.message.message_id)
        except: pass
            
        try: 
            bot.send_message(int(target_uid), f"<tg-emoji emoji-id=\"5463260230861202209\">🟥</tg-emoji> <b>Sipariş İptal Edildi!</b>\n🔖 Sipariş ID: <code>#{order_id}</code>\n<tg-emoji emoji-id=\"5348227245599105972\">💼</tg-emoji> Ürün: <b>{item_name}</b>\n<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> <b>{cost} Puan</b> cüzdanınıza iade edildi.")
        except: pass
        bot.answer_callback_query(call.id)
        return


    if call.data == "nav_referral":
        bot_user = bot.get_me().username
        link = f"https://t.me/{bot_user}?start={uid}"
        is_vip = db["users"].get(uid, {}).get("is_vip", False)
        puan_txt = "<b>+2 Puan</b> (VIP Avantajı! '<tg-emoji emoji-id=\"6266995104687330978\">👍</tg-emoji>')" if is_vip else "<b>+1 Puan</b>"
        
        kb = InlineKeyboardMarkup()
        kb.row(InlineKeyboardButton(" Ana Merkeze Dön", callback_data="nav_main"))
        
        txt = (f"<tg-emoji emoji-id=\"6034834452843074121\">🤝</tg-emoji> <b>Davet Et, Kazan!</b>\n\n"
               f"<tg-emoji emoji-id=\"6147439566107186310\">👇</tg-emoji> Aşağıdaki kişisel linkinizle arkadaşlarınızı sisteme davet edin, "
               f"her yeni katılımda anında {puan_txt} kazanın.\n\n"
               f"<tg-emoji emoji-id=\"6071278787947925866\">📋</tg-emoji> <b>Sizin Linkiniz:</b>\n<code>{link}</code>")
        try:
            bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(chat_id, txt, reply_markup=kb)
        bot.answer_callback_query(call.id)
        return
        

    elif call.data == "nav_redeem":
        msg = bot.send_message(call.message.chat.id, "<tg-emoji emoji-id=\"5418010521309815154\">🎫</tg-emoji> <b>Promosyon/Kupon Kodunuzu Giriniz:</b>")
        bot.register_next_step_handler(msg, lambda m: redeem_gift_code(m, uid))

    elif call.data == "nav_help":
        txt = (
            "<tg-emoji emoji-id=\"5807488863064559221\">📖</tg-emoji> <b>YARDIM MERKEZİ</b> <tg-emoji emoji-id=\"5807488863064559221\">📖</tg-emoji>\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "<tg-emoji emoji-id=\"5350699789551935589\">🛍</tg-emoji> <b>Mağaza Nedir</b> <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji>\n"
            "Botun ana satış alanıdır. Kategoriler halinde düzenlenmiş ürünleri buradan satın alabilirsiniz. "
            "Bir ürüne tıklayınca fiyat ve stok bilgisi çıkar, satın al butonuna basınca puan düşülür ve siparişiniz oluşur.\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> <b>Puan Nasıl Kazanılır</b> <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji>\n"
            "• Davet linkinizle arkadaş getirince <b>+1 Puan</b>\n"
            "• Admin tarafından manuel puan yüklenmesiyle\n"
            "• Promosyon kodu kullanarak\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "<tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> <b>Sipariş Takibi Nasıl Çalışır <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji></b>\n"
            "Satın aldığınız her ürün için otomatik bir <b>Sipariş ID</b> oluşturulur.\n"
            "<b>Sipariş Geçmişi</b> menüsünden siparişlerinizi görebilirsiniz.\n\n"
            "Sipariş durumları:\n"
            "<tg-emoji emoji-id=\"5415803109983133508\">🟡</tg-emoji> <b>Alındı</b> — Siparişiniz sisteme kaydedildi\n"
            "<tg-emoji emoji-id=\"5415896658665808854\">🔵</tg-emoji> <b>İşlemde</b> — Yönetici siparişinizi hazırlıyor\n"
            "<tg-emoji emoji-id=\"5415722549281561774\">🟢</tg-emoji> <b>Teslim Edildi</b> — Ürün size iletildi\n"
            "<tg-emoji emoji-id=\"5463260230861202209\">🟥</tg-emoji> <b>İptal</b> — Sipariş iptal edildi, puan iade edildi\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "<tg-emoji emoji-id=\"5418010521309815154\">🎫</tg-emoji> <b>Promosyon Kodu Nedir?</b> <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji>\n"
            "Yönetici tarafından oluşturulan özel kodlardır. "
            "Ana menüden <b>Promosyon Kodu</b> butonuna basarak kodunuzu girin ve puan kazanın. "
            "Her kod sadece belirtilen kişi sayısınca kullanılabilir.\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "<tg-emoji emoji-id=\"6215452159945740230\">🤝</tg-emoji> <b>Davet Et Kazan Nedir</b> <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji>\n"
            "Size özel davet linkinizi paylaşın. Linkinizle bota ilk kez giren ve kanallara katılan "
            "her kişi için otomatik olarak <b>+1 Puan</b> kazanırsınız.\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "<tg-emoji emoji-id=\"5787517290907962993\">💸</tg-emoji> <b>Bakiye İadesi Nedir</b> <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji>\n"
            "Hatalı sipariş veya sorun yaşarsanız ana menüden <b>Bakiye İadesi</b> butonuna basarak "
            "yöneticiye talebinizi iletebilirsiniz.\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "<tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji> <b>Destek İçin:</b> Admin butonu üzerinden ulaşabilirsiniz <tg-emoji emoji-id=\"5780742388020419424\">⁉️</tg-emoji>"
        )
        kb = InlineKeyboardMarkup()
        kb.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(call.message.chat.id, txt, reply_markup=kb)
        bot.answer_callback_query(call.id)

    elif call.data == "nav_products_list":
        products = db.get("products", {})
        if not products:
            txt = "📋 <b>Ürün Listesi</b>\n\nŞu an stokta ürün bulunmuyor."
        else:
            def stock_emoji(s):
                if s == 0: return "❌"
                elif s <= 3: return "🔴"
                elif s <= 10: return "🟡"
                else: return "🟢"
            
            kategoriler = {}
            for pk, pdata in products.items():
                cat = pdata.get("category", "genel")
                kategoriler.setdefault(cat, []).append(pdata)
            
            cat_isimleri = db.get("categories", {})
            txt = "📋 <b>Ürün Listesi</b>\n\n"
            for cat_key, urunler in kategoriler.items():
                cat_raw = cat_isimleri.get(cat_key, cat_key)
                cat_isim = cat_raw["name"] if isinstance(cat_raw, dict) else cat_raw
                txt += f"<b>{cat_isim}</b>\n"
                for p in urunler:
                    s = p.get("stock", 0)
                    txt += f"{stock_emoji(s)} {p['name']} — <b>{p['price']}💎</b>\n"
                txt += "\n"
            txt += "🟢 Stoklu  🟡 Az Kaldı (≤10)  🔴 Son Stok (≤3)  ❌ Tükendi"
        
        kb = InlineKeyboardMarkup()
        kb.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(call.message.chat.id, txt, reply_markup=kb)
        bot.answer_callback_query(call.id)

    elif call.data == "nav_lang":
        bot.edit_message_text("<tg-emoji emoji-id=\"5399898266265475100\">🌍</tg-emoji> Lütfen dil tercihinizi yapın:", call.message.chat.id, call.message.message_id, reply_markup=get_language_keyboard())

    elif call.data == "nav_support":
        msg = bot.send_message(call.message.chat.id, "<tg-emoji emoji-id=\"5251684060186569219\">🔔</tg-emoji> <b>7/24 VIP Destek Hattı</b>\n\nLütfen talebinizi detaylı olarak yazın:")
        bot.register_next_step_handler(msg, send_support_message_step, uid)

    elif call.data == "nav_refund":
        history = db["users"][uid].get("order_history", [])[:5]
        hist_txt = "Kayıtlarda harcama bulunamadı." if not history else "\n".join(history)
        msg_text = f"<tg-emoji emoji-id=\"6086980694460861135\">💸</tg-emoji> <b>Bakiye İade Merkezi</b>\n\n<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> <b>Mevcut Bakiyeniz:</b> {db['users'][uid]['balance']} Puan\n\n<tg-emoji emoji-id=\"5258477770735885832\">📄</tg-emoji> <b>Son İşlemleriniz:</b>\n<code>{hist_txt}</code>\n\nİade talep ettiğiniz işlemi yazınız:"
        msg = bot.send_message(call.message.chat.id, msg_text)
        bot.register_next_step_handler(msg, send_refund_message_step, uid)

    elif call.data == "nav_transfer":
        u = db["users"].get(uid, {})
        today = datetime.now().strftime("%Y-%m-%d")
        t_date = u.get("last_transfer_date", "")
        t_count = u.get("daily_transfer_count", 0) if t_date == today else 0
        MAX_TRANSFER = 2
        kalan = MAX_TRANSFER - t_count

        m2 = InlineKeyboardMarkup()
        m2.row(pbtn(" Ana Merkeze Dön", "nav_main", emoji_id="5253997076169115797", style="danger"))

        if kalan <= 0:
            txt = (f" <b>Puan Transfer</b>\n\n"
                   f"<tg-emoji emoji-id=\"5981091707456851997\">⏳</tg-emoji> Bugünkü 2 transfer hakkınızı kullandınız!\n"
                   f"Yarın tekrar kullanabilirsiniz.")
            try: bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m2)
            except: bot.send_message(chat_id, txt, reply_markup=m2)
            bot.answer_callback_query(call.id)
            return

        m2.row(pbtn(f" Transfer Yap ({kalan} hak kaldı)", "nav_transfer_do", emoji_id="5780834596673296534", style="success"))
        txt = (f"<tg-emoji emoji-id=\"6267068789146260253\">💰</tg-emoji> <b>Puan Transfer Sistemi</b>\n\n"
               f"<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> <b>Bakiyeniz:</b> {u.get('balance', 0)} Puan\n"
               f"<tg-emoji emoji-id=\"5981091707456851997\">⏳</tg-emoji> <b>Günlük Hak:</b> {kalan}/{MAX_TRANSFER} kaldı\n\n"
               f"<tg-emoji emoji-id=\"5271725159273752548\">1️⃣</tg-emoji> Her transferde bot <b>1 Puan komisyon</b> keser.\n"
               f"<tg-emoji emoji-id=\"6032994772321309200\">👤</tg-emoji> Alıcı ID ve miktarı girerek transfer yapın.")
        try: bot.edit_message_text(txt, chat_id, call.message.message_id, reply_markup=m2)
        except: bot.send_message(chat_id, txt, reply_markup=m2)
        bot.answer_callback_query(call.id)

    elif call.data == "nav_transfer_do":
        u = db["users"].get(uid, {})
        today = datetime.now().strftime("%Y-%m-%d")
        t_date = u.get("last_transfer_date", "")
        t_count = u.get("daily_transfer_count", 0) if t_date == today else 0
        if t_count >= 2:
            bot.answer_callback_query(call.id, "⏳ Bugünkü transfer hakkınız doldu!", show_alert=True)
            return
        msg = bot.send_message(chat_id,
            f"<tg-emoji emoji-id=\"6267068789146260253\">💰</tg-emoji> <b>Transfer Bilgisi Girin</b>\n\n"
            f"Format: <code>AlıcıID|Miktar</code>\nÖrn: <code>1234567|10</code>\n\n"
            f"<tg-emoji emoji-id=\"5271801931814165886\">⚠️</tg-emoji> Bot <b>1 Puan komisyon</b> keser.\n"
            f"<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> Bakiyeniz: {u.get('balance', 0)} Puan\n\n"
            f"<i>İptal: /iptal</i>")
        bot.register_next_step_handler(msg, transfer_step, uid)
        bot.answer_callback_query(call.id)

    elif call.data == "nav_leaderboard":
        sorted_users = sorted(db["users"].items(), key=lambda x: x[1]['balance'], reverse=True)[:10]
        txt = "<tg-emoji emoji-id=\"5893376775781617954\">🏆</tg-emoji> <b>Elit Liderler Tablosu (Top 10)</b>\n\n"
        for i, (user_id, data) in enumerate(sorted_users, 1):
            medal = "<tg-emoji emoji-id=\"6123126147086556656\">🥇</tg-emoji>" if i == 1 else "<tg-emoji emoji-id=\"5251227187335424668\">🥈</tg-emoji>" if i == 2 else "<tg-emoji emoji-id=\"5251282841521647446\">🥉</tg-emoji>" if i == 3 else "🔸"
            txt += f"{medal} ID: {user_id} | <tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> {data['balance']} | <tg-emoji emoji-id=\"6034834452843074121\">🤝</tg-emoji> {data['refs']} Davet\n"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(" Ana Merkeze Dön", callback_data="nav_main")))
        
    elif int(uid) in ADMIN_IDS and call.data.startswith("adm_"):
        handle_admin_callbacks(call)

    elif call.data.startswith("lang_"):
        lang = call.data.split("_")[1]
        db["users"][uid]["language"] = lang
        save_database(db)
        kb, txts = get_main_keyboard(uid)
        bot.edit_message_text(f"<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> Dil güncellendi.\n\n{txts['welcome']}", call.message.chat.id, call.message.message_id, reply_markup=kb)


# ============================================================
# ⚙️ GELİŞMİŞ ADMİN PROTOKOLLERİ
# ============================================================

def handle_admin_callbacks(call):
    uid = str(call.from_user.id)
    if int(uid) not in ADMIN_IDS: return

    if call.data == "adm_dashboard":
        bot.edit_message_text("⚙️ <b>Gelişmiş Yönetim Merkezine Hoşgeldiniz:</b>", call.message.chat.id, call.message.message_id, reply_markup=get_admin_keyboard())

    elif call.data == "adm_active_orders":
        aktif = []
        for u_id, udata in db.get("users", {}).items():
            for oid, odata in udata.get("orders", {}).items():
                if odata.get("durum") in ["alindi", "islemde"]:
                    aktif.append((u_id, oid, odata))
        
        if not aktif:
            kb = InlineKeyboardMarkup()
            kb.row(pbtn(" Yenile", "adm_active_orders", emoji_id="6325541629260206557"),
                   pbtn(" Panel", "adm_dashboard", emoji_id="5253997076169115797"))
            try:
                bot.edit_message_text("📋 <b>Aktif Siparişler</b>\n\n✅ Şu an bekleyen sipariş yok.", call.message.chat.id, call.message.message_id, reply_markup=kb)
            except:
                bot.send_message(call.message.chat.id, "📋 <b>Aktif Siparişler</b>\n\n✅ Şu an bekleyen sipariş yok.", reply_markup=kb)
            bot.answer_callback_query(call.id)
            return
        
        kb = InlineKeyboardMarkup()
        _durum_emoji_id = {
            "alindi":  "5778479949572738874",
            "islemde": "5956229471585441542",
            "teslim":  "6041720006973067267",
            "iptal":   "5314504236132747481"
        }
        for u_id, oid, odata in aktif[-20:]:
            d = odata.get("durum", "alindi")
            btn_txt = f"#{oid} — {odata.get('urun','?')[:20]}"
            kb.row(pbtn(btn_txt, f"adm_order_{u_id}_{oid}", emoji_id=_durum_emoji_id.get(d, "5778479949572738874"), style="primary"))
        
        kb.row(
            pbtn("Yenile", "adm_active_orders", emoji_id="6325541629260206557"),
            pbtn("Panel",  "adm_dashboard",     emoji_id="5253997076169115797")
        )
        
        txt = f"📋 <b>Aktif Siparişler</b> ({len(aktif)} adet)\n\n🟡 Alındı  🔵 İşlemde\n\nBir siparişe tıklayarak işlem yapın:"
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(call.message.chat.id, txt, reply_markup=kb)
        bot.answer_callback_query(call.id)

    elif call.data.startswith("adm_order_"):
        parts = call.data.split("_", 3)
        t_uid = parts[2]
        oid   = parts[3]
        
        odata = db.get("users", {}).get(t_uid, {}).get("orders", {}).get(oid)
        if not odata:
            bot.answer_callback_query(call.id, "⚠️ Sipariş bulunamadı!", show_alert=True)
            return
        
        d = odata.get("durum", "alindi")
        durum_yazi = {"alindi": "🟡 Alındı", "islemde": "🔵 İşlemde", "teslim": "✅ Teslim", "iptal": "❌ İptal"}
        urun_key = odata.get("urun_key", "")
        
        txt = (f"<tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> <b>Sipariş Detayı (Admin)</b>\n\n"
               f"<tg-emoji emoji-id=\"6287264550005773857\">🔖</tg-emoji> Sipariş ID: <code>#{oid}</code>\n"
               f"<tg-emoji emoji-id=\"6032994772321309200\">👤</tg-emoji> Kullanıcı ID: <code>{t_uid}</code>\n"
               f"<tg-emoji emoji-id=\"5350699789551935589\">🛍</tg-emoji> Ürün: <b>{odata.get('urun','?')}</b>\n"
               f"<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> Fiyat: {odata.get('fiyat',0)} Puan\n"
               f"<tg-emoji emoji-id=\"5028418466000930064\">📆</tg-emoji> Tarih: {odata.get('tarih','-')}\n"
               f"<tg-emoji emoji-id=\"6129402906782207599\">📊</tg-emoji> Durum: <b>{durum_yazi.get(d, d)}</b>")
        
        kb = InlineKeyboardMarkup()
        if d == "alindi":
            kb.row(pbtn("İşleme Al", f"adm_setstat_{t_uid}_{oid}_islemde", emoji_id="5956229471585441542", style="primary"))
        if d in ["alindi", "islemde"]:
            kb.row(
                pbtn("Teslim Et", f"adm_deliver_{t_uid}_{oid}_{urun_key}", emoji_id="6041720006973067267", style="success"),
                pbtn("İptal Et",  f"adm_cancel_{t_uid}_{oid}_{urun_key}",  emoji_id="5314504236132747481", style="danger")
            )
        kb.row(pbtn("Listeye Dön", "adm_active_orders", emoji_id="5253997076169115797", style="primary"))
        
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(call.message.chat.id, txt, reply_markup=kb)
        bot.answer_callback_query(call.id)

    elif call.data.startswith("adm_setstat_"):
        parts = call.data.split("_", 4)
        t_uid     = parts[2]
        oid       = parts[3]
        yeni_d    = parts[4]
        
        if t_uid in db["users"] and oid in db["users"][t_uid].get("orders", {}):
            db["users"][t_uid]["orders"][oid]["durum"] = yeni_d
            save_database(db)
        
        durum_mesaj = {"islemde": "<tg-emoji emoji-id=\"5415896658665808854\">🔵</tg-emoji> Siparişiniz işleme alındı!", "teslim": "<tg-emoji emoji-id=\"5415722549281561774\">🟢</tg-emoji> Siparişiniz teslim edildi!"}
        try: bot.send_message(int(t_uid), f"{durum_mesaj.get(yeni_d,'<tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> Siparişiniz güncellendi.')}\n<tg-emoji emoji-id=\"6287264550005773857\">🔖</tg-emoji> Sipariş ID: <code>#{oid}</code>")
        except: pass
        
        bot.answer_callback_query(call.id, f"<tg-emoji emoji-id=\"5415722549281561774\">🟢</tg-emoji> Durum güncellendi: {yeni_d}", show_alert=True)
        handle_admin_callbacks(type('obj', (object,), {'data': f'adm_order_{t_uid}_{oid}', 'message': call.message, 'from_user': call.from_user, 'id': call.id})())

    elif call.data.startswith("adm_deliver_"):
        parts = call.data.split("_", 4)
        t_uid    = parts[2]
        oid      = parts[3]
        urun_key = parts[4]
        odata = db.get("users", {}).get(t_uid, {}).get("orders", {}).get(oid, {})
        item_name = odata.get("urun", urun_key)
        admin_name = call.from_user.first_name or "Yönetim"
        
        user_link = db.get("users", {}).get(t_uid, {}).get("orders", {}).get(oid, {}).get("link", "—")
        msg = bot.send_message(call.message.chat.id,
            f"<tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> <b>#{oid}</b> — <b>{item_name}</b>\n"
            f"<tg-emoji emoji-id=\"5780406047416174369\">🔗</tg-emoji> Kullanıcı Linki: {user_link}\n\n"
            f"<tg-emoji emoji-id=\"5465443379917629504\">🔓</tg-emoji> <b>Müşteriye gönderilecek TESLİMAT bilgisini yazın:</b>\n<i>(/iptal için /iptal)</i>")
        original_text = call.message.text or ""
        bot.register_next_step_handler(msg, lambda m: admin_deliver_order_step(
            m, t_uid, item_name, call.message.message_id, call.message.chat.id, admin_name, original_text, oid))
        bot.answer_callback_query(call.id)

    elif call.data.startswith("adm_cancel_"):
        parts = call.data.split("_", 4)
        t_uid    = parts[2]
        oid      = parts[3]
        urun_key = parts[4]
        
        odata = db.get("users", {}).get(t_uid, {}).get("orders", {}).get(oid, {})
        cost = odata.get("fiyat", 0)
        item_name = odata.get("urun", urun_key)
        
        if t_uid in db["users"]:
            db["users"][t_uid]["balance"] += cost
            if oid in db["users"][t_uid].get("orders", {}):
                db["users"][t_uid]["orders"][oid]["durum"] = "iptal"
            save_database(db)
        
        try: bot.send_message(int(t_uid),
            f"<tg-emoji emoji-id=\"5895410404141568046\">❎</tg-emoji> <b>Sipariş İptal Edildi!</b>\n<tg-emoji emoji-id=\"6287264550005773857\">🔖</tg-emoji> Sipariş ID: <code>#{oid}</code>\n"
            f"<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> <b>{cost} Puan</b> cüzdanınıza iade edildi.")
        except: pass
        
        bot.answer_callback_query(call.id, "<tg-emoji emoji-id=\"5895410404141568046\">❎</tg-emoji> Sipariş iptal edildi, puan iade edildi.", show_alert=True)
        fake_call = type('obj', (object,), {'data': 'adm_active_orders', 'message': call.message, 'from_user': call.from_user, 'id': call.id})()
        handle_admin_callbacks(fake_call)
    
    elif call.data == "adm_add_category":
        msg = bot.send_message(call.message.chat.id, "📂 <b>Yeni Kategori Ekle</b>\nFormat: <code>kategori_kodu|<tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> Kategori Adı</code>\nÖrn: <code>sosyal|📱 Sosyal Medya</code>\n\n⚠️ Kod boşluksuz, küçük harfle olmalı.")
        bot.register_next_step_handler(msg, admin_add_category_step)

    elif call.data == "adm_del_category":
        categories = db.get("categories", {})
        if not categories:
            bot.answer_callback_query(call.id, "⚠️ Hiç kategori yok!", show_alert=True)
            return
        cat_list = list(categories.items())
        lines = [f"<code>{i+1}</code>. {(v['name'] if isinstance(v, dict) else v)}  <i>({k})</i>" for i, (k, v) in enumerate(cat_list)]
        msg = bot.send_message(call.message.chat.id, "🗂️ <b>Kategori Silme Paneli</b>\n\nSilmek istediğiniz kategorinin numarasını yazın:\n\n" + "\n".join(lines))
        bot.register_next_step_handler(msg, admin_del_category_step, cat_list)

    elif call.data == "adm_ban_user":
        msg = bot.send_message(call.message.chat.id, "🚫 <b>Banlanacak Kullanıcı ID girin:</b>")
        bot.register_next_step_handler(msg, lambda m: admin_ban_step(m, True))
        
    elif call.data == "adm_unban_user":
        msg = bot.send_message(call.message.chat.id, "🔓 <b>Banı Kaldırılacak Kullanıcı ID girin:</b>")
        bot.register_next_step_handler(msg, lambda m: admin_ban_step(m, False))

    elif call.data == "adm_add_product":
        categories = db.get("categories", {"genel": " Genel"})
        cat_list = "\n".join([f"  <code>{k}</code> → {v}" for k, v in categories.items()])
        msg = bot.send_message(call.message.chat.id, f"🛒 <b>Eklenecek Ürün Bilgilerini Yazın</b>\nFormat: <code>kod|Ürün Adı|Fiyat|Stok|kategori_kodu</code>\nÖrn: <code>netflix|Netflix Premium|15|50|genel</code>\n\n📂 <b>Mevcut Kategoriler:</b>\n{cat_list}")
        bot.register_next_step_handler(msg, admin_add_product_step)

    elif call.data == "adm_del_all_products":
        products = db.get("products", {})
        if not products:
            bot.answer_callback_query(call.id, "⚠️ Mağazada hiç ürün yok!", show_alert=True)
            return
        product_list = list(products.items())
        lines = [f"<code>{i+1}</code>. {data['name']} — 💎{data['price']} Puan | 📦 Stok: {data.get('stock', 99)}"
                 for i, (pk, data) in enumerate(product_list)]
        list_text = ("🗑️ <b>Toplu Ürün Silme Paneli</b>\n\n"
                     "Silmek istediğiniz ürün numaralarını <b>virgülle</b> yazın.\n"
                     "Tümünü silmek için <code>hepsi</code> yazın.\n\n"
                     "Örn: <code>1,3,5</code>\n\n" + "\n".join(lines))
        msg = bot.send_message(call.message.chat.id, list_text)
        bot.register_next_step_handler(msg, admin_del_all_products_step, product_list)

    elif call.data == "adm_del_product":
        products = db.get("products", {})
        if not products:
            bot.answer_callback_query(call.id, "⚠️ Mağazada hiç ürün yok!", show_alert=True)
            return
        product_list = list(products.items())
        lines = [f"<code>{i+1}</code>. {data['name']} — 💎{data['price']} Puan | 📦 Stok: {data.get('stock', 99)}  <i>({pk})</i>"
                 for i, (pk, data) in enumerate(product_list)]
        list_text = "🗑️ <b>Ürün Silme Paneli</b>\n\nAşağıdan silmek istediğiniz ürünün <b>numarasını</b> yazın:\n\n" + "\n".join(lines)
        msg = bot.send_message(call.message.chat.id, list_text)
        bot.register_next_step_handler(msg, admin_del_product_step, product_list)

    elif call.data == "adm_add_vip_product":
        vip_cats = db.get("vip_categories", {})
        if not vip_cats:
            bot.answer_callback_query(call.id, "⚠️ Önce VIP Kategori ekleyin!", show_alert=True)
            return
        cat_list_txt = "\n".join([f"  <code>{k}</code> → {(v['name'] if isinstance(v,dict) else v)}" for k,v in vip_cats.items()])
        msg = bot.send_message(call.message.chat.id,
            f"<tg-emoji emoji-id=\"6005862519019673214\">👑</tg-emoji> <b>VIP Ürün Ekle</b>\n"
            f"Format: <code>kod|Ad|Fiyat|Stok|vip_kategori_kodu</code>\n"
            f"Örn: <code>vip_item1|VIP Paket|50|10|vip_genel</code>\n\n"
            f"<b>Mevcut VIP Kategoriler:</b>\n{cat_list_txt}")
        bot.register_next_step_handler(msg, admin_add_vip_product_step)

    elif call.data == "adm_del_vip_product":
        vip_products = db.get("vip_products", {})
        if not vip_products:
            bot.answer_callback_query(call.id, "⚠️ VIP mağazada ürün yok!", show_alert=True)
            return
        product_list = list(vip_products.items())
        lines = [f"<code>{i+1}</code>. {d['name']} — <tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji>{d['price']} Puan | 📦 Stok: {d.get('stock',0)}"
                 for i,(pk,d) in enumerate(product_list)]
        msg = bot.send_message(call.message.chat.id,
            "<tg-emoji emoji-id=\"6005862519019673214\">👑</tg-emoji> <b>VIP Ürün Sil</b>\n\n"
            "Silmek istediğiniz ürün numarasını veya <code>hepsi</code> yazın:\n\n" + "\n".join(lines))
        bot.register_next_step_handler(msg, admin_del_vip_product_step, product_list)

    elif call.data == "adm_add_vip_category":
        msg = bot.send_message(call.message.chat.id,
            "<tg-emoji emoji-id=\"6005862519019673214\">👑</tg-emoji> <b>VIP Kategori Ekle</b>\n"
            "Format: <code>kategori_kodu|👑 Kategori Adı</code>\n"
            "Örn: <code>vip_sosyal|👑 VIP Sosyal Medya</code>")
        bot.register_next_step_handler(msg, admin_add_vip_category_step)

    elif call.data == "adm_del_vip_category":
        vip_cats = db.get("vip_categories", {})
        if not vip_cats:
            bot.answer_callback_query(call.id, "⚠️ VIP kategori yok!", show_alert=True)
            return
        cat_list = list(vip_cats.items())
        lines = [f"<code>{i+1}</code>. {(v['name'] if isinstance(v,dict) else v)} <i>({k})</i>"
                 for i,(k,v) in enumerate(cat_list)]
        msg = bot.send_message(call.message.chat.id,
            "<tg-emoji emoji-id=\"6005862519019673214\">👑</tg-emoji> <b>VIP Kategori Sil</b>\n\n"
            "Silmek istediğiniz kategorinin numarasını yazın:\n\n" + "\n".join(lines))
        bot.register_next_step_handler(msg, admin_del_vip_category_step, cat_list)

    elif call.data == "adm_give_prem":
        msg = bot.send_message(call.message.chat.id,
            "👑 <b>VIP Verilecek Kullanıcı ID girin:</b>\n\n"
            "<i>VIP avantajları:\n• Günde 2x Günlük Bonus\n• Davette +2 Puan\n• VIP Mağazaya erişim</i>")
        bot.register_next_step_handler(msg, lambda m: admin_premium_step(m, True))

    elif call.data == "adm_take_prem":
        msg = bot.send_message(call.message.chat.id, "❌ <b>VIP'i Kaldırılacak Kullanıcı ID girin:</b>")
        bot.register_next_step_handler(msg, lambda m: admin_premium_step(m, False))

    elif call.data == "adm_add_balance":
        msg = bot.send_message(call.message.chat.id, "💎 <b>Puan Eklenecek Kullanıcı ID ve Miktarı Yazın</b>\nFormat: <code>ID|Puan</code>\nÖrn: <code>1234567|50</code>")
        bot.register_next_step_handler(msg, lambda m: admin_balance_step(m, "add"))

    elif call.data == "adm_sub_balance":
        msg = bot.send_message(call.message.chat.id, "🗑️ <b>Puanı Silinecek Kullanıcı ID ve Miktarı Yazın</b>\nFormat: <code>ID|Puan</code>\nÖrn: <code>1234567|20</code>")
        bot.register_next_step_handler(msg, lambda m: admin_balance_step(m, "sub"))

    elif call.data == "adm_broadcast":
        msg = bot.send_message(call.message.chat.id, "📢 <b>Tüm Kullanıcılara Gönderilecek Toplu Duyuru Mesajını Yazın:</b>")
        bot.register_next_step_handler(msg, admin_broadcast_step)

    elif call.data == "adm_send_msg":
        msg = bot.send_message(call.message.chat.id, "✉️ <b>Bottan Kullanıcıya Direkt Mesaj Gönderme</b>\nFormat: <code>ID|Mesajınız</code>\nÖrn: <code>1234567|Hesabınız onaylandı.</code>")
        bot.register_next_step_handler(msg, admin_send_msg_step)

    elif call.data == "adm_create_gift":
        msg = bot.send_message(call.message.chat.id, 
            "🎫 <b>Kupon Kodu Oluştur</b>\n\n"
            "Format: <code>KOD|PUAN|LİMİT|GÜN|SAAT</code>\n\n"
            "📌 Örnekler:\n"
            "<code>KAMPANYA25|50|100|7|0</code> → 7 gün geçerli\n"
            "<code>FLASH|10|5|0|6</code> → 6 saat geçerli\n"
            "<code>SINIRSIZKOD|20|999|0|0</code> → Süresiz\n\n"
            "<i>Gün ve saat 0 girilirse süresizdir.</i>"
        )
        bot.register_next_step_handler(msg, admin_create_gift_step)

    elif call.data == "adm_list_users":
        users = db.get("users", {})
        total = len(users)
        if total == 0:
            bot.answer_callback_query(call.id, "⚠️ Hiç kayıtlı kullanıcı yok!", show_alert=True)
            return
        lines = []
        for i, (uid_key, udata) in enumerate(users.items(), 1):
            premium = "👑" if udata.get("is_premium") else "👤"
            banned = " 🚫" if udata.get("is_banned") else ""
            lines.append(f"{premium} <code>{uid_key}</code> | 💎{udata.get('balance', 0)}{banned}")
        chunks = [lines[i:i+30] for i in range(0, len(lines), 30)]
        bot.send_message(call.message.chat.id, f"👥 <b>Kayıtlı Kullanıcılar — Toplam: {total}</b>")
        for chunk in chunks:
            bot.send_message(call.message.chat.id, "\n".join(chunk))

    elif call.data == "adm_stats":
        total_users = len(db.get("users", {}))
        txt = f"📊 <b>Sistem Analiz Raporu</b>\n\n👥 Toplam Kayıtlı Kullanıcı: {total_users}\n📦 Aktif Stokta Ürün Türü: {len(db.get('products', {}))}"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=get_admin_keyboard())

    elif call.data == "adm_bot_status":
        db["bot_status"] = "maintenance" if db.get("bot_status", "active") == "active" else "active"
        save_database(db)
        bot.answer_callback_query(call.id, f"Sistem Durumu: {db['bot_status'].upper()}", show_alert=True)
        bot.edit_message_text(f"⚙️ Yönetim Paneli\nBot Durumu Değişti: <b>{db['bot_status'].upper()}</b>", call.message.chat.id, call.message.message_id, reply_markup=get_admin_keyboard())

    elif call.data == "adm_add_admin":
        if not is_owner(uid):
            bot.answer_callback_query(call.id, "❌ Sadece Owner admin ekleyebilir!", show_alert=True)
            return
        msg = bot.send_message(call.message.chat.id, 
            "👑 <b>Admin Ekle</b>\n\n"
            "Format: <code>ID|SEVİYE</code>\n\n"
            "Seviyeler:\n"
            "• <b>owner</b> - Tüm haklar (silinemez)\n"
            "• <b>super_admin</b> - Ürün/kategori yönetimi\n"
            "• <b>admin</b> - Sadece sipariş işleme\n\n"
            "Örn: <code>123456789|super_admin</code>"
        )
        bot.register_next_step_handler(msg, admin_add_admin_step, uid)

    elif call.data == "adm_del_admin":
        if not is_owner(uid):
            bot.answer_callback_query(call.id, "❌ Sadece Owner admin silebilir!", show_alert=True)
            return
        if len(ADMIN_LEVELS) <= 1:
            bot.answer_callback_query(call.id, "⚠️ En az 1 admin kalmalı!", show_alert=True)
            return
        lines = []
        for i, (aid, level) in enumerate(ADMIN_LEVELS.items()):
            emoji = "👑" if level == "owner" else "⭐" if level == "super_admin" else "🔧"
            lines.append(f"<code>{i+1}</code>. {emoji} <code>{aid}</code> (<b>{level}</b>)")
        msg = bot.send_message(call.message.chat.id, 
            "🗑️ <b>Admin Sil</b>\n\n"
            "⚠️ Owner silinemez!\n\n"
            "Silmek istediğiniz adminin <b>numarasını</b> yazın:\n\n" + "\n".join(lines)
        )
        bot.register_next_step_handler(msg, admin_del_admin_step, uid)

    elif call.data == "adm_list_admins":
        lines = []
        for aid, level in ADMIN_LEVELS.items():
            emoji = "👑" if level == "owner" else "⭐" if level == "super_admin" else "🔧"
            txt = f"{emoji} <code>{aid}</code> - <b>{level}</b>"
            if level == "owner":
                txt += " (Silinemez)"
            lines.append(txt)
        txt = "👑 <b>Mevcut Admin Listesi</b>\n\n" + "\n".join(lines)
        kb = InlineKeyboardMarkup()
        kb.row(pbtn(" Panele Dön", "adm_dashboard", emoji_id="5253997076169115797"))
        try:
            bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=kb)
        except:
            bot.send_message(call.message.chat.id, txt, reply_markup=kb)
        bot.answer_callback_query(call.id)

def admin_ban_step(m, status):
    target = m.text.strip()
    if target in db["users"]:
        db["users"][target]["is_banned"] = status
        save_database(db)
        bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> Kullanıcı ({target}) Durumu Güncellendi: Banned={status}")
    else: bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"6221914376329237010\">⚠️</tg-emoji> Kullanıcı bulunamadı.")

def admin_add_product_step(m):
    try:
        parts = [p.strip() for p in m.text.split("|")]
        if len(parts) < 5:
            raise ValueError("Eksik parametre (min 5 gerekli)")
        
        pk = parts[0]
        name = parts[1]
        price = int(parts[2])
        stock = int(parts[3])
        category = parts[4]
        emoji_id = parts[5] if len(parts) > 5 else "5373251851074415873"
        color = parts[6] if len(parts) > 6 else "primary"
        
        if category not in db.get("categories", {}):
            bot.send_message(m.chat.id, f"❌ <code>{category}</code> kategorisi bulunamadı.")
            return
        
        db["products"][pk] = {
            "name": name,
            "price": price,
            "stock": stock,
            "category": category,
            "emoji_id": emoji_id,
            "color": color
        }
        save_database(db)
        cat_raw = db["categories"][category]
        cat_name = cat_raw["name"] if isinstance(cat_raw, dict) else cat_raw
        
        bot.send_message(m.chat.id,
            f"<tg-emoji emoji-id=\"5415722549281561774\">🟢</tg-emoji> Ürün eklendi!\n"
            f"<b>{name}</b>\n"
            f"<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> {price} Puan | 📦 Stok: {stock}\n"
            f"<tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> {cat_name}\n"
            f"<tg-emoji emoji-id=\"5310039132297242441\">🎨</tg-emoji> Renk: {color} | Emoji ID: {emoji_id}"
        )
    except Exception as e:
        bot.send_message(m.chat.id,
            f"❌ Hatalı format.\n<code>{e}</code>\n\n"
            "Format: <code>ANAHTAR|AD|FİYAT|STOK|KATEGORİ|EMOJİ_ID|RENK</code>\n"
            "Örn: <code>tool1|Yeni Tool|15|50|tool_urunler|5188481279963715781|danger</code>\n\n"
            "<i>EMOJİ_ID ve RENK opsiyonel (varsayılan: 5373251851074415873, primary)</i>"
        )

def admin_add_category_step(m):
    try:
        parts = m.text.split("|", 1)
        key = parts[0].strip().lower().replace(" ", "_")
        name = parts[1].strip() if len(parts) >= 2 else key
        if key in db.get("categories", {}):
            bot.send_message(m.chat.id, f"⚠️ <code>{key}</code> kategorisi zaten mevcut!")
            return
        db.setdefault("categories", {})[key] = {"name": name, "emoji_id": "6129402906782207599", "color": "primary"}
        save_database(db)
        bot.send_message(m.chat.id, f"✅ Kategori eklendi!\n📂 <b>{name}</b>  <code>({key})</code>")
    except:
        bot.send_message(m.chat.id, "❌ Hatalı format. Örn: <code>sosyal|📱 Sosyal Medya</code>")

def admin_del_category_step(m, cat_list):
    try:
        idx = int(m.text.strip()) - 1
        if idx < 0 or idx >= len(cat_list):
            bot.send_message(m.chat.id, f"❌ Geçersiz numara. 1 ile {len(cat_list)} arasında girin.")
            return
        key, cat_data = cat_list[idx]
        cat_name = cat_data["name"] if isinstance(cat_data, dict) else cat_data
        if key == "genel":
            bot.send_message(m.chat.id, "❌ <b>Genel</b> kategorisi silinemez.")
            return
        del db["categories"][key]
        for pk, pdata in db.get("products", {}).items():
            if pdata.get("category") == key:
                db["products"][pk]["category"] = "genel"
        save_database(db)
        bot.send_message(m.chat.id, f"✅ <b>{cat_name}</b> kategorisi silindi.\n⚠️ Bu kategorideki ürünler <b>Genel</b>'e taşındı.")
    except ValueError:
        bot.send_message(m.chat.id, "❌ Lütfen sadece bir numara girin.")

def admin_del_all_products_step(m, product_list):
    try:
        text = m.text.strip().lower()
        if text == "hepsi":
            sayi = len(product_list)
            db["products"] = {}
            save_database(db)
            bot.send_message(m.chat.id, f"✅ Toplam <b>{sayi} ürün</b> mağazadan silindi.")
            return
        numaralar = [int(x.strip()) for x in text.split(",")]
        gecersiz = [n for n in numaralar if n < 1 or n > len(product_list)]
        if gecersiz:
            bot.send_message(m.chat.id, f"❌ Geçersiz numara: {gecersiz}. Lütfen 1 ile {len(product_list)} arasında girin.")
            return
        silinenler = []
        for n in sorted(set(numaralar)):
            pk, data = product_list[n - 1]
            if pk in db.get("products", {}):
                del db["products"][pk]
                silinenler.append(f"<b>{data['name']}</b>")
        save_database(db)
        bot.send_message(m.chat.id, f"✅ {len(silinenler)} ürün silindi:\n" + "\n".join(silinenler))
    except ValueError:
        bot.send_message(m.chat.id, "❌ Hatalı format. Örn: <code>1,3,5</code> ya da <code>hepsi</code>")

def admin_del_product_step(m, product_list):
    try:
        idx = int(m.text.strip()) - 1
        if idx < 0 or idx >= len(product_list):
            bot.send_message(m.chat.id, f"❌ Geçersiz numara. Lütfen 1 ile {len(product_list)} arasında bir sayı girin.")
            return
        pk, data = product_list[idx]
        if pk in db.get("products", {}):
            del db["products"][pk]
            save_database(db)
            bot.send_message(m.chat.id, f"✅ <b>#{idx+1} — {data['name']}</b> ürünü mağazadan başarıyla silindi.")
        else:
            bot.send_message(m.chat.id, "❌ Ürün artık mevcut değil, silinmiş olabilir.")
    except ValueError:
        bot.send_message(m.chat.id, "❌ Lütfen sadece bir numara girin. (Örn: <code>3</code>)")

def admin_premium_step(m, status):
    target = m.text.strip()
    if target in db["users"]:
        db["users"][target]["is_vip"] = status
        db["users"][target]["is_premium"] = status
        save_database(db)
        durum_txt = "VERİLDİ ✅" if status else "KALDIRILDI ❌"
        bot.send_message(m.chat.id,
            f"👑 <b>VIP {durum_txt}</b>\n"
            f"👤 Kullanıcı ID: <code>{target}</code>\n\n"
            f"{'✅ Avantajlar: Günde 2x Bonus | +2 Davet Puanı | VIP Mağaza' if status else '❌ VIP üyelik sonlandırıldı.'}")
        try:
            if status:
                bot.send_message(int(target),
                    "👑 <b>Tebrikler! VIP üyeliğiniz aktif edildi!</b>\n\n"
                    "'<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' <b>VIP Avantajlarınız:</b>\n"
                    "'<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' Günde <b>2 kez</b> günlük bonus alabilirsiniz\n"
                    "'<tg-emoji emoji-id=\"6120625823285251747\">👍</tg-emoji>' Her davet için <b>+2 Puan</b> kazanırsınız\n"
                    "'<tg-emoji emoji-id=\"6120635817674149717\">👍</tg-emoji>' <b>VIP Mağaza</b>'ya erişim açıldı!\n\n"
                    "<i>İyi kullanmalar! 🚀</i>")
            else:
                bot.send_message(int(target),
                    " '<tg-emoji emoji-id=\"6120660741369369103\">👍</tg-emoji>'   <b>VIP üyeliğiniz sonlandırıldı.</b>\n"
                    "<i>Detaylı bilgi için yöneticiyle iletişime geçin.</i>")
        except: pass
    else:
        bot.send_message(m.chat.id, "❌ Kullanıcı bulunamadı. ID'yi kontrol edin.")

def admin_balance_step(m, mode):
    try:
        target, amt = m.text.split("|")
        target = target.strip(); amt = int(amt.strip())
        if target in db["users"]:
            if mode == "add": db["users"][target]["balance"] += amt
            else: db["users"][target]["balance"] = max(0, db["users"][target]["balance"] - amt)
            save_database(db)
            yeni_bakiye = db["users"][target]["balance"]
            bot.send_message(m.chat.id, f"✅ İşlem Başarılı! {target} yeni bakiyesi: {yeni_bakiye}")
            try: bot.send_message(int(target), f"<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> Hesabınıza yönetim tarafından <b>{amt} puan</b> eklendi!" if mode == "add" else f"<tg-emoji emoji-id=\"4958534924278694938\">🗑</tg-emoji> Hesabınızdan yönetim tarafından <b>{amt} puan</b> silindi.")
            except: pass
            if mode == "add":
                notify_admins(f"💰 <b>BAKİYE YÜKLEMESİ YAPILDI</b>\n👤 Kullanıcı ID: <code>{target}</code>\n💎 Eklenen: <b>{amt} Puan</b>\n📊 Yeni Bakiye: <b>{yeni_bakiye} Puan</b>")
        else: bot.send_message(m.chat.id, "❌ Kullanıcı bulunamadı.")
    except: bot.send_message(m.chat.id, "❌ Hatalı format.")

def admin_broadcast_step(m):
    text = m.text
    threading.Thread(target=notify_everyone, args=(text,)).start()
    bot.send_message(m.chat.id, "📢 Toplu duyuru işlemi arka planda başlatıldı!")

def admin_send_msg_step(m):
    try:
        target, msg_text = m.text.split("|", 1)
        target = target.strip()
        bot.send_message(int(target), f"<tg-emoji emoji-id=\"5253742260054409879\">✉️</tg-emoji> <b>Yönetimden Gelen Mesaj:</b>\n\n{msg_text.strip()}", parse_mode="HTML")
        bot.send_message(m.chat.id, f"✅ Mesaj <code>{target}</code> kullanıcısına başarıyla iletildi.")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Mesaj gönderilemedi.\n<code>{e}</code>\n\nFormat: <code>ID|Mesajınız</code>")

def admin_create_gift_step(m):
    try:
        parts = [p.strip() for p in m.text.split("|")]
        if len(parts) < 3:
            raise ValueError("Eksik parametre")
        
        kod  = parts[0].upper().replace(" ", "")
        puan = int(parts[1])
        limit = int(parts[2])
        gun  = int(parts[3]) if len(parts) > 3 else 0
        saat = int(parts[4]) if len(parts) > 4 else 0
        
        if not kod:
            raise ValueError("Kod boş olamaz")
        
        if kod in db.get("gift_codes", {}):
            bot.send_message(m.chat.id, f"⚠️ <code>{kod}</code> kodu zaten mevcut! Farklı bir kod girin.")
            return
        
        bitis = None
        if gun > 0 or saat > 0:
            toplam_saniye = (gun * 86400) + (saat * 3600)
            bitis = time.time() + toplam_saniye
        
        if "gift_codes" not in db: db["gift_codes"] = {}
        db["gift_codes"][kod] = {
            "puan": puan,
            "limit": limit,
            "used_by": [],
            "bitis": bitis
        }
        save_database(db)
        
        sure_txt = "Süresiz" if not bitis else f"{gun} gün {saat} saat" if gun > 0 else f"{saat} saat"
        bot.send_message(m.chat.id, 
            f"<tg-emoji emoji-id=\"5418010521309815154\">🎫</tg-emoji> <b>Kupon Oluşturuldu!</b>\n\n"
            f"<tg-emoji emoji-id=\"5307843983102204243\">🔑</tg-emoji> Kod: <code>{kod}</code>\n"
            f"<tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> Değer: <b>{puan} Puan</b>\n"
            f"<tg-emoji emoji-id=\"6032994772321309200\">👤</tg-emoji> Kullanım Limiti: <b>{limit} Kişi</b>\n"
            f"<tg-emoji emoji-id=\"5981091707456851997\">⏳</tg-emoji> Geçerlilik: <b>{sure_txt}</b>"
        )
    except Exception as e:
        bot.send_message(m.chat.id, 
            f"❌ Hatalı format.\n<code>{e}</code>\n\n"
            "Format: <code>KOD|PUAN|LİMİT|GÜN|SAAT</code>\n"
            "Örn: <code>KAMPANYA25|50|100|7|0</code>\n"
            "<i>(Gün ve saat 0 = süresiz)</i>"
        )

@bot.message_handler(content_types=['new_chat_members', 'text'])
def master_message_handler(m):
    if m.chat.type in ['group', 'supergroup']:
        return

    if m.chat.type == 'private':
        uid = str(m.from_user.id)
        
        if db.get("bot_status", "active") != "active" and m.from_user.id not in ADMIN_IDS:
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5440621591387980068\">🔜</tg-emoji> Sistem bakımda.")
            return
            
        uid = str(m.from_user.id)
        chat_id = m.chat.id

        ref = None
        if m.text and m.text.startswith("/start"):
            ref = m.text.split()[1] if len(m.text.split()) > 1 else None

        is_new_user = uid not in db.get("users", {})
        check_user_exists(uid, ref)

        if m.text and m.text.startswith("/start"):
            
            if is_new_user or db["users"][uid].get("status") == "pending":
                db["users"][uid]["status"] = "pending"
                save_database(db)
                send_math_captcha(chat_id, uid, ref)
                return
                
            if REQUIRED_CHANNELS and not is_member_of_channels(m.from_user.id):
                bot.send_message(
                    chat_id, 
                    "<tg-emoji emoji-id=\"6242353099193718277\">📣</tg-emoji> <b>Bota erişmek için aşağıdaki kanallara katılman gerekiyor!</b>\n"
                    "Katıldıktan sonra <tg-emoji emoji-id=\"6325541629260206557\">🔄</tg-emoji> butonuna bas <tg-emoji emoji-id=\"6222198028854367391\">👇</tg-emoji>", 
                    reply_markup=get_channel_join_keyboard()
                )
                return
                
            pending = db["users"].get(uid, {}).get("pending_ref")
            if pending:
                award_referral(uid, pending)
                db["users"][uid].pop("pending_ref", None)
                save_database(db)
                
            kb, txts = get_main_keyboard(uid)
            bot.send_message(chat_id, txts['welcome'], reply_markup=kb)
            return

        elif m.text == "/panel" and int(uid) in ADMIN_IDS:
            bot.send_message(chat_id, "⚙️ <b>Yönetim Merkezine Hoşgeldiniz:</b>", reply_markup=get_admin_keyboard())
            return

        else:
            if REQUIRED_CHANNELS and not is_member_of_channels(m.from_user.id):
                bot.send_message(chat_id, "<tg-emoji emoji-id=\"5780405967527089720\">📢</tg-emoji> <b>Bota erişmek için aşağıdaki kanallara katılman gerekiyor!</b>", reply_markup=get_channel_join_keyboard())
                return

            kb, txts = get_main_keyboard(uid)
            bot.send_message(chat_id, txts['welcome'], reply_markup=kb)

def admin_deliver_order_step(m, target_uid, item_name, orig_msg_id, admin_chat_id, admin_name, original_text, order_id="?"):
    if m.text == "/iptal": 
        bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"6221914376329237010\">⚠️</tg-emoji> Teslimat iptal edildi.")
        return
    if target_uid in db["users"] and order_id in db["users"][target_uid].get("orders", {}):
        db["users"][target_uid]["orders"][order_id]["durum"] = "teslim"
        db["users"][target_uid]["orders"][order_id]["not"] = m.text[:200]
        save_database(db)
    try:
        bot.edit_message_text(f"{original_text}\n\n✅ <b>Durum: {admin_name} Tarafından TESLİM EDİLDİ</b>", chat_id=admin_chat_id, message_id=orig_msg_id)
    except: pass
    try:
        bot.send_message(int(target_uid), 
            f"<tg-emoji emoji-id=\"5251227707026470504\">🎁</tg-emoji> <b>Siparişiniz Teslim Edildi!</b>\n"
            f"'<tg-emoji emoji-id=\"6120946172010959542\">👍</tg-emoji>' Sipariş ID: <code>#{order_id}</code>\n"
            f"<tg-emoji emoji-id=\"5212947303467345789\">📦</tg-emoji> Ürün: {item_name}\n"
            f"<tg-emoji emoji-id=\"5465443379917629504\">🔓</tg-emoji> <b>Teslimat Bilgisi:</b>\n<code>{m.text}</code>"
        )
    except: pass

def send_refund_message_step(m, uid):
    bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"6028565819225542441\">✅</tg-emoji> İade talebiniz iletildi.")
    notify_admins(f"💳 <b>İADE TALEBİ!</b>\n👤 ID: <code>{uid}</code>\n📝 Mesaj: {m.text}")

def send_support_message_step(m, uid):
    bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"6028565819225542441\">✅</tg-emoji> Mesajınız destek ekibine iletildi.")
    notify_admins(f"🛎️ <b>DESTEK TALEBİ!</b>\n👤 ID: <code>{uid}</code>\n💬 Mesaj: {m.text}")

def redeem_gift_code(m, uid):
    code = m.text.strip().upper()
    if code in db.get("gift_codes", {}):
        coupon = db["gift_codes"][code]
        
        bitis = coupon.get("bitis")
        if bitis and time.time() > bitis:
            del db["gift_codes"][code]
            save_database(db)
            bot.send_message(m.chat.id, "⏳ <b>Bu kuponun süresi dolmuş!</b>")
            return
        
        if uid in coupon.get("used_by", []):
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"6221914376329237010\">⚠️</tg-emoji> Bu kuponu daha önce zaten kullandınız!")
            return
        if len(coupon.get("used_by", [])) >= coupon["limit"]:
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"6221914376329237010\">⚠️</tg-emoji> Bu kuponun kullanım limiti dolmuş!")
            return
        bonus = coupon["puan"]
        db["users"][uid]["balance"] += bonus
        coupon.setdefault("used_by", []).append(uid)
        if len(coupon["used_by"]) >= coupon["limit"]:
            del db["gift_codes"][code]
        save_database(db)
        bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"5418010521309815154\">🎫</tg-emoji> <b>Kupon Başarılı!</b> Hesabınıza <b>+{bonus} Puan</b> 💎 eklendi.")
    else: 
        bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5348514879558926674\">👎</tg-emoji> Geçersiz, süresi dolmuş veya hatalı kupon kodu.")

def admin_add_admin_step(m, owner_uid):
    try:
        parts = m.text.strip().split("|")
        if len(parts) < 2:
            bot.send_message(m.chat.id, "❌ Format: <code>ID|SEVİYE</code>\nÖrn: <code>123456789|super_admin</code>")
            return
        
        new_admin_id = str(int(parts[0].strip()))
        level = parts[1].strip().lower()
        
        if level not in ["owner", "super_admin", "admin"]:
            bot.send_message(m.chat.id, "❌ Geçersiz seviye! Kullan: owner, super_admin, admin")
            return
        
        if new_admin_id in ADMIN_LEVELS:
            bot.send_message(m.chat.id, f"⚠️ <code>{new_admin_id}</code> zaten admin listesinde!")
            return
        
        ADMIN_LEVELS[new_admin_id] = level
        ADMIN_IDS.append(int(new_admin_id))
        
        emoji = "👑" if level == "owner" else "⭐" if level == "super_admin" else "🔧"
        bot.send_message(m.chat.id, 
            f"✅ <code>{new_admin_id}</code> eklendi!\n"
            f"{emoji} <b>Seviye:</b> {level}\n\n"
            f"⚠️ <b>Not:</b> Kalıcı yapmak için dosyada ADMIN_LEVELS'e ekleyin."
        )
    except ValueError:
        bot.send_message(m.chat.id, "❌ Geçersiz format! <code>ID|SEVİYE</code> yazın.")

def admin_del_admin_step(m, owner_uid):
    try:
        idx = int(m.text.strip()) - 1
        admin_list = list(ADMIN_LEVELS.items())
        
        if idx < 0 or idx >= len(admin_list):
            bot.send_message(m.chat.id, f"❌ Geçersiz numara. 1 ile {len(admin_list)} arasında girin.")
            return
        
        aid, level = admin_list[idx]
        
        if level == "owner":
            bot.send_message(m.chat.id, "❌ Owner silinemez! Bu çok tehlikeli.")
            return
        
        del ADMIN_LEVELS[aid]
        if int(aid) in ADMIN_IDS:
            ADMIN_IDS.remove(int(aid))
        
        bot.send_message(m.chat.id, 
            f"✅ <code>{aid}</code> silindi.\n\n"
            f"⚠️ <b>Not:</b> Dosyada ADMIN_LEVELS'den de silin."
        )
    except ValueError:
        bot.send_message(m.chat.id, "❌ Lütfen sadece bir numara girin.")


def transfer_step(m, sender_uid):
    if m.text and m.text.strip().lower() == "/iptal":
        bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"6221914376329237010\">⚠️</tg-emoji> Transfer iptal edildi.")
        return
    try:
        parts = m.text.strip().split("|")
        if len(parts) < 2:
            raise ValueError("Format hatalı")
        target_uid = parts[0].strip()
        amount = int(parts[1].strip())

        if target_uid == sender_uid:
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Kendinize transfer yapamazsınız!")
            return
        if target_uid not in db.get("users", {}):
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Alıcı kullanıcı bulunamadı!")
            return
        if amount <= 0:
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Miktar 0'dan büyük olmalı!")
            return

        COMMISSION = 1
        total_needed = amount + COMMISSION
        sender_balance = db["users"][sender_uid].get("balance", 0)

        if sender_balance < total_needed:
            bot.send_message(m.chat.id,
                f"<tg-emoji emoji-id=\"5348514879558926674\">👎</tg-emoji> <b>Yetersiz Bakiye!</b>\n"
                f"Gerekli: <b>{total_needed} Puan</b> ({amount} + {COMMISSION} komisyon)\n"
                f"Bakiyeniz: <b>{sender_balance} Puan</b>")
            return

        today = datetime.now().strftime("%Y-%m-%d")
        t_date = db["users"][sender_uid].get("last_transfer_date", "")
        t_count = db["users"][sender_uid].get("daily_transfer_count", 0) if t_date == today else 0
        if t_count >= 2:
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5981091707456851997\">⏳</tg-emoji> Bugünkü 2 transfer hakkınızı kullandınız!")
            return

        db["users"][sender_uid]["balance"] -= total_needed
        db["users"][target_uid]["balance"] += amount

        if t_date == today:
            db["users"][sender_uid]["daily_transfer_count"] = t_count + 1
        else:
            db["users"][sender_uid]["daily_transfer_count"] = 1
            db["users"][sender_uid]["last_transfer_date"] = today

        save_database(db)

        kalan = 2 - db["users"][sender_uid]["daily_transfer_count"]
        bot.send_message(m.chat.id,
            f"<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> <b>Transfer Başarılı!</b>\n\n"
            f"<tg-emoji emoji-id=\"6032994772321309200\">👤</tg-emoji> <b>Alıcı ID:</b> <code>{target_uid}</code>\n"
            f"<tg-emoji emoji-id=\"6267068789146260253\">💰</tg-emoji> <b>Gönderilen:</b> {amount} Puan\n"
            f"<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> <b>Komisyon:</b> {COMMISSION} Puan\n"
            f"<tg-emoji emoji-id=\"5215420556089776398\">📊</tg-emoji> <b>Yeni Bakiyeniz:</b> {db['users'][sender_uid]['balance']} Puan\n\n"
            f"<tg-emoji emoji-id=\"5981091707456851997\">⏳</tg-emoji> Bugün için <b>{kalan} transfer hakkınız</b> kaldı."
        )
        try:
            bot.send_message(int(target_uid),
                f"<tg-emoji emoji-id=\"6267068789146260253\">💰</tg-emoji> <b>Puan Transferi Aldınız!</b>\n\n"
                f"<tg-emoji emoji-id=\"5780834596673296534\">➕</tg-emoji> <b>+{amount} Puan</b> hesabınıza eklendi!\n"
                f"<tg-emoji emoji-id=\"6032994772321309200\">👤</tg-emoji> <b>Gönderen:</b> <code>{sender_uid}</code>\n"
                f"<tg-emoji emoji-id=\"5251562950698759162\">💎</tg-emoji> <b>Yeni Bakiyeniz:</b> {db['users'][target_uid]['balance']} Puan"
            )
        except: pass

    except ValueError:
        bot.send_message(m.chat.id,
            "<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Hatalı format!\n"
            "Doğru format: <code>AlıcıID|Miktar</code>\nÖrn: <code>1234567|10</code>")
    except Exception as e:
        bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Hata: <code>{e}</code>")


def admin_add_vip_product_step(m):
    try:
        parts = [p.strip() for p in m.text.split("|")]
        if len(parts) < 5:
            raise ValueError("Eksik parametre (min 5 gerekli)")
        pk = parts[0]; name = parts[1]; price = int(parts[2])
        stock = int(parts[3]); category = parts[4]
        emoji_id = parts[5] if len(parts) > 5 else "6005862519019673214"
        color = parts[6] if len(parts) > 6 else "danger"

        if category not in db.get("vip_categories", {}):
            bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> VIP kategori bulunamadı: <code>{category}</code>\nÖnce VIP Kategori Ekle!")
            return

        db.setdefault("vip_products", {})[pk] = {
            "name": name, "price": price, "stock": stock,
            "category": category, "emoji_id": emoji_id, "color": color
        }
        save_database(db)
        cat_raw = db["vip_categories"][category]
        cat_name = cat_raw["name"] if isinstance(cat_raw, dict) else cat_raw
        bot.send_message(m.chat.id,
            f"<tg-emoji emoji-id=\"6005862519019673214\">👑</tg-emoji> <b>VIP Ürün Eklendi!</b>\n"
            f"<b>{name}</b> | <tg-emoji emoji-id=\"6325717349257187998\">💎</tg-emoji> {price} Puan | <tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> Stok: {stock}\n"
            f"<tg-emoji emoji-id=\"5854908544712707500\">📦</tg-emoji> Kategori: {cat_name}")
    except Exception as e:
        bot.send_message(m.chat.id,
            f"<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Hatalı format: <code>{e}</code>\n"
            "Format: <code>kod|Ad|Fiyat|Stok|vip_kategori|emoji_id|renk</code>")

def admin_del_vip_product_step(m, product_list):
    try:
        text = m.text.strip().lower()
        if text == "hepsi":
            db["vip_products"] = {}
            save_database(db)
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> Tüm VIP ürünler silindi.")
            return
        idx = int(text) - 1
        if idx < 0 or idx >= len(product_list):
            bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Geçersiz numara!")
            return
        pk, data = product_list[idx]
        if pk in db.get("vip_products", {}):
            del db["vip_products"][pk]
            save_database(db)
            bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> <b>{data['name']}</b> VIP mağazadan silindi.")
        else:
            bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Ürün bulunamadı.")
    except ValueError:
        bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Lütfen bir numara veya 'hepsi' girin.")

def admin_add_vip_category_step(m):
    try:
        parts = m.text.split("|", 1)
        key = parts[0].strip().lower().replace(" ", "_")
        name = parts[1].strip() if len(parts) >= 2 else key
        if key in db.get("vip_categories", {}):
            bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"6221914376329237010\">⚠️</tg-emoji> <code>{key}</code> VIP kategorisi zaten var!")
            return
        db.setdefault("vip_categories", {})[key] = {"name": name, "emoji_id": "6005862519019673214", "color": "danger"}
        save_database(db)
        bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"6005862519019673214\">👑</tg-emoji> VIP Kategori eklendi: <b>{name}</b> <code>({key})</code>")
    except:
        bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Hatalı format. Örn: <code>vip_sosyal|👑 VIP Sosyal Medya</code>")

def admin_del_vip_category_step(m, cat_list):
    try:
        idx = int(m.text.strip()) - 1
        if idx < 0 or idx >= len(cat_list):
            bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Geçersiz numara!")
            return
        key, cat_data = cat_list[idx]
        cat_name = cat_data["name"] if isinstance(cat_data, dict) else cat_data
        del db["vip_categories"][key]
        for pk, pdata in db.get("vip_products", {}).items():
            if pdata.get("category") == key:
                db["vip_products"][pk]["category"] = "vip_genel"
        save_database(db)
        bot.send_message(m.chat.id, f"<tg-emoji emoji-id=\"5350572310627632617\">✅</tg-emoji> VIP Kategori <b>{cat_name}</b> silindi.")
    except ValueError:
        bot.send_message(m.chat.id, "<tg-emoji emoji-id=\"5314504236132747481\">❌</tg-emoji> Lütfen bir numara girin.")


# ============================================================
# 🌐 FASTAPI WEB SUNUCUSU (RENDER 7/24 AKTİF TUTMA)
# ============================================================

app = FastAPI(title="VANTORIUM Telegram Bot API")


@app.get("/")
def home():
    return {
        "status": "Bot ve API 7/24 aktif çalışıyor!",
        "bot_status": db.get("bot_status", "active"),
        "timestamp": str(datetime.now())
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """İsteğe bağlı webhook endpoint (ileride kullanılabilir)."""
    try:
        data = await request.json()
        update = telebot.types.Update.de_json(data)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_telegram_bot():
    print("🚀 VANTORIUM BOT arka planda polling ile başlatılıyor...")
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
        except Exception as e:
            print(f"⚠️ Bot polling hatası: {e} — 5 saniye sonra tekrar denenecek...")
            time.sleep(5)


@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=run_telegram_bot, daemon=True)
    t.start()
    print("✅ Telegram bot thread başlatıldı.")


# ================= RENDER İÇİN UVICORN ÇALIŞTIRMA =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("__main__:app", host="0.0.0.0", port=port, reload=False)
