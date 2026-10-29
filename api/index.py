from flask import Flask, request
import os, psycopg2, re, requests
from datetime import datetime

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID") # ID Telegram lu, ambil di @userinfobot

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

def send_message(chat_id, text, thread_id=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if thread_id:
        payload["message_thread_id"] = thread_id
    requests.post(url, json=payload)

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
        sender_username = sender.get('username','').lower()
        sender_id = sender.get('id')
        first_name = sender.get('first_name','')
        chat_title = chat_info.get('title','Private')

        # LOG SEMUA AKTIVITAS
        save_log(sender_id, sender_username, first_name, chat_id, chat_title, thread_id, "message", text)

        if text.startswith('/start'):
            save_log(sender_id, sender_username, first_name, chat_id, chat_title, thread_id, "START", text)
            send_message(chat_id, f"👋 Bot Aktif!\n\nHalo @{sender_username}\n\nNama :\nUsername :\nJob :\nSpek :\n\n/cek @user\n/hapus @user\n/logs\n/stats", thread_id)
            return {"ok": True}

        # === FITUR KHUSUS OWNER ===
        if text.startswith('/logs') or text.startswith('/stats'):
            # Cek owner (opsional, kalau OWNER_ID belum di set, semua bisa)
            if OWNER_ID and str(sender_id) != str(OWNER_ID):
                send_message(chat_id, "⛔ Hanya owner!", thread_id)
                return {"ok": True}
            
            conn = get_db()
            cur = conn.cursor()
            
            # Hitung total
            cur.execute("SELECT COUNT(DISTINCT user_id) FROM bot_logs WHERE action='START'")
            total_start = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT chat_id) FROM bot_logs")
            total_group = cur.fetchone()[0]
            
            # Ambil 20 log terakhir yang klik start
            cur.execute("""
                SELECT username, first_name, chat_title, created_at, action 
                FROM bot_logs WHERE action='START' 
                ORDER BY id DESC LIMIT 15
            """)
            starts = cur.fetchall()
            
            # Ambil grup mana aja bot connect
            cur.execute("""
                SELECT DISTINCT chat_id, chat_title, COUNT(*) as total_msg 
                FROM bot_logs 
                GROUP BY chat_id, chat_title 
                ORDER BY total_msg DESC LIMIT 10
            """)
            groups = cur.fetchall()
            cur.close()
            conn.close()

            msg = f"<b>📊 STATS BOT</b>\n\n"
            msg += f"Total /start : {total_start} user\n"
            msg += f"Total Grup : {total_group} grup\n\n"
            
            msg += f"<b>👥 15 Orang Terakhir Klik Start:</b>\n"
            for u, fn, ct, dt, act in starts:
                msg += f"- @{u} ({fn}) - {ct} - {dt.strftime('%d/%m %H:%M')}\n"
            
            msg += f"\n<b>📍 Bot Connect Kemana:</b>\n"
            for gid, gtitle, cnt in groups:
                msg += f"- {gtitle} (ID:{gid}) - {cnt} pesan\n"
            
            send_message(chat_id, msg, thread_id)
            return {"ok": True}

        if text.lower().startswith('/cek'):
            m = re.search(r'@([A-Za-z0-9_]+)', text)
            uname = m.group(1).lower() if m else (text.split()[1].lower().replace('@','') if len(text.split())>1 else None)
            if not uname:
                send_message(chat_id, "❓ /cek @username", thread_id)
                return {"ok": True}
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT nama, job, spek FROM verifikasi_list WHERE username=%s", (uname,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                send_message(chat_id, f"✅ <b>VERIFIED</b>\nNama: {row[0]}\nUsername: @{uname}\nJob: {row[1]}\nSpek: {row[2]}", thread_id)
            else:
                send_message(chat_id, f"❌ @{uname} BELUM VERIF", thread_id)
            return {"ok": True}

        if text.lower().startswith('/hapus'):
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
                send_message(chat_id, f"✅ <b>Berhasil!</b>\nNama: {nama.group(1).strip()}\nUsername: @{uname}\nJob: {job.group(1).strip() if job else '-'}\nSpek: {spek.group(1).strip() if spek else '-'}", thread_id)
                return {"ok": True}

        # AUTO DELETE
        if thread_id in PROTECTED_TOPICS:
            if text.startswith('/'): return {"ok": True}
            if not is_verified(sender_username):
                delete_message(chat_id, message_id)
                send_message(chat_id, f"⛔ @{sender_username} pesan dihapus! Belum verifikasi.\n\nVerif di topic 54:\nNama :\nUsername :\nJob :\nSpek :", thread_id)
                return {"ok": True}

        return {"ok": True}
    except Exception as e:
        print("ERROR:", e)
        return {"ok": True}

@app.route('/', methods=['GET'])
def home():
    return "Bot v6 + Logger Aktif"

if __name__ == "__main__":
    app.run()