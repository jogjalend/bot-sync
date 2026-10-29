from flask import Flask, request
import os, psycopg2, re, requests
from PIL import Image, ImageDraw, ImageFont
import random

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")

PROTECTED_TOPICS = [7245, 1328, 6848, 413, 4, 1745, 4843, 5250, 410]

def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS verifikasi_list (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            nama TEXT,
            job TEXT,
            spek TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bot_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            username TEXT,
            first_name TEXT,
            chat_id BIGINT,
            chat_title TEXT,
            thread_id BIGINT,
            action TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# === FUNGSI BIKIN FOTO TULISAN ===
def create_text_image(text_username, action="/start"):
    W, H = 800, 450
    # Warna random keren
    colors = [(30,30,46), (17,24,39), (88,28,135), (15,23,42), (120,40,40)]
    bg = random.choice(colors)
    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)
    
    # Coba load font bold, fallback default
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Tulis
    draw.text((50, 30), f"{action} DETECTED", font=font_small, fill=(160,160,255))
    draw.text((50, 120), f"author :", font=font_small, fill=(200,200,200))
    draw.text((50, 160), f"@{text_username}", font=font_big, fill=(255,255,255))
    draw.text((50, 280), f"JogjaLend Sync Bot", font=font_small, fill=(150,150,150))
    
    # Garis hiasan
    draw.rectangle([50, 350, 750, 360], fill=(100,100,255))

    path = f"/tmp/{text_username}_{action}.png"
    img.save(path)
    return path

def send_message(chat_id, text, thread_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if thread_id:
        payload["message_thread_id"] = thread_id
    requests.post(url, json=payload)

def send_photo_with_text(chat_id, image_path, caption, thread_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(image_path, 'rb') as f:
        files = {'photo': f}
        data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        if thread_id:
            data["message_thread_id"] = thread_id
        requests.post(url, data=data, files=files)

def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    requests.post(url, json={"chat_id": chat_id, "message_id": message_id})

def is_verified(username):
    if not username: return False
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM verifikasi_list WHERE username=%s", (username.lower(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row)

def save_log(user_id, username, first_name, chat_id, chat_title, thread_id, action, msg=""):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO bot_logs (user_id, username, first_name, chat_id, chat_title, thread_id, action, message)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (user_id, username, first_name, chat_id, chat_title, thread_id, action, msg[:500]))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("LOG ERROR:", e)

@app.route('/api/index', methods=['POST'])
def webhook():
    try:
        init_db()
        data = request.json
        message = data.get('message') or data.get('edited_message')
        if not message:
            return {"ok": True}
        
        chat_id = message['chat']['id']
        message_id = message['message_id']
        text = message.get('text','').strip()
        thread_id = message.get('message_thread_id')
        sender = message.get('from', {})
        chat_info = message.get('chat', {})
        sender_username = sender.get('username','').lower() or f"user{sender.get('id')}"
        sender_id = sender.get('id')
        first_name = sender.get('first_name','')
        chat_title = chat_info.get('title','Private')

        save_log(sender_id, sender_username, first_name, chat_id, chat_title, thread_id, "message", text)

        if text.startswith('/start'):
            save_log(sender_id, sender_username, first_name, chat_id, chat_title, thread_id, "START", text)
            # BIKIN FOTO
            img_path = create_text_image(sender_username, "/start")
            send_photo_with_text(chat_id, img_path, f"👋 Bot Aktif!\nHalo <b>@{sender_username}</b>", thread_id)
            send_message(chat_id, f"Nama :\nUsername :\nJob :\nSpek :\n\n/cek @user\n/hapus @user\n/logs\n/stats", thread_id)
            return {"ok": True}

        if text.startswith('/logs') or text.startswith('/stats'):
            if OWNER_ID and str(sender_id) != str(OWNER_ID):
                send_message(chat_id, "⛔ Hanya owner!", thread_id)
                return {"ok": True}
            
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT COUNT(DISTINCT user_id) FROM bot_logs WHERE action='START'")
            total_start = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT chat_id) FROM bot_logs")
            total_group = cur.fetchone()[0]
            cur.execute("""
                SELECT user_id, username, first_name, chat_title, created_at 
                FROM bot_logs WHERE action='START' 
                ORDER BY id DESC LIMIT 10
            """)
            starts = cur.fetchall()
            cur.close()
            conn.close()

            send_message(chat_id, f"📊 <b>STATS BOT</b>\nTotal /start : {total_start}\nTotal Grup : {total_group}\n\nKirim foto log...", thread_id)
            
            for uid, uname, fn, ct, dt in starts:
                img_path = create_text_image(uname or f"{fn}", "/start")
                caption = f"author : @{uname}\nname : {fn}\nchat : {ct}\n{dt.strftime('%d/%m %H:%M')}"
                send_photo_with_text(chat_id, img_path, caption, thread_id)
            return {"ok": True}

        if text.lower().startswith('/cek'):
            # BIKIN FOTO JUGA UNTUK /cek
            img_path = create_text_image(sender_username, "/cek")
            send_photo_with_text(chat_id, img_path, f"author : @{sender_username}\nmengecek verifikasi", thread_id)
            
            m = re.search(r'@([A-Za-z0-9_]+)', text)
            uname = m.group(1).lower() if m else (text.split()[1].lower().replace('@','') if len(text.split())>1 else None)
            if not uname: return {"ok": True}
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT nama, job, spek FROM verifikasi_list WHERE username=%s", (uname,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                send_message(chat_id, f"✅ @{uname} VERIFIED", thread_id)
            else:
                send_message(chat_id, f"❌ @{uname} BELUM VERIF", thread_id)
            return {"ok": True}

        if text.lower().startswith('/hapus'):
            img_path = create_text_image(sender_username, "/hapus")
            send_photo_with_text(chat_id, img_path, f"author : @{sender_username}", thread_id)
            m = re.search(r'@([A-Za-z0-9_]+)', text)
            uname = m.group(1).lower() if m else (text.split()[1].lower().replace('@','') if len(text.split())>1 else None)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM verifikasi_list WHERE username=%s", (uname,))
            conn.commit()
            cur.close()
            conn.close()
            send_message(chat_id, f"🗑️ @{uname} dihapus!", thread_id)
            return {"ok": True}

        if 'Nama' in text and 'Username' in text and 'Job' in text:
            nama = re.search(r'Nama\s*:\s*(.*)', text, re.I)
            username = re.search(r'Username\s*:\s*@?(\S+)', text, re.I)
            job = re.search(r'Job\s*:\s*(.*)', text, re.I)
            spek = re.search(r'Spek\s*:\s*(.*)', text, re.I)
            if nama and username:
                uname = username.group(1).lower().strip('@ ,')
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO verifikasi_list (username, nama, job, spek)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET nama=%s, job=%s, spek=%s
                """, (uname, nama.group(1).strip(), job.group(1).strip() if job else '-', spek.group(1).strip() if spek else '-', nama.group(1).strip(), job.group(1).strip() if job else '-', spek.group(1).strip() if spek else '-'))
                conn.commit()
                cur.close()
                conn.close()
                img_path = create_text_image(uname, "VERIFIED")
                send_photo_with_text(chat_id, img_path, f"✅ Berhasil Verif @{uname}", thread_id)
                return {"ok": True}

        if thread_id in PROTECTED_TOPICS:
            if text.startswith('/'): return {"ok": True}
            if not is_verified(sender_username):
                delete_message(chat_id, message_id)
                img_path = create_text_image(sender_username, "BLOCKED")
                send_photo_with_text(chat_id, img_path, f"⛔ @{sender_username} pesan dihapus! Belum verifikasi.\nVerif di topic 54:\nNama :\nUsername :\nJob :\nSpek :", thread_id)
                return {"ok": True}

        return {"ok": True}
    except Exception as e:
        print("ERROR:", e)
        return {"ok": True}

@app.route('/', methods=['GET'])
def home():
    return "Bot v8 Text Image Aktif"

if __name__ == "__main__":
    app.run()