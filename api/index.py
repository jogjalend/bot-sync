from flask import Flask, request
import os, psycopg2, re, requests

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
GROUP_ID = int(os.getenv("JOGJALEND_GROUP_ID", "-1003920359218"))
THREAD_ID = int(os.getenv("VERIF_THREAD_ID", "54"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

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
            cabang TEXT,
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

@app.route('/api/index', methods=['POST'])
def webhook():
    try:
        init_db()
        data = request.json
        message = data.get('message') or data.get('edited_message')
        if not message:
            return {"ok": True}
        
        chat_id = message['chat']['id']
        text = message.get('text','').strip()
        thread_id = message.get('message_thread_id')

        if text.startswith('/start'):
            send_message(chat_id,
                "👋 <b>Bot Sync JogjaLend Aktif!</b>\n\n"
                f"📍 Grup ID: <code>{GROUP_ID}</code>\n"
                f"📌 Topic Verif: {THREAD_ID}\n\n"
                "Ketik /help untuk daftar perintah",
                thread_id)
            return {"ok": True}

        if text.startswith('/help'):
            send_message(chat_id,
                "📖 <b>Perintah Bot Sync:</b>\n\n"
                "1. <b>Input Data (di Topic 54)</b>\n"
                "Nama: Budi\n"
                "Username: @budi\n"
                "Cabang: Jogja\n\n"
                "2. /cek @username - Cek data user\n"
                "3. /hapus @username - Hapus data\n"
                "4. /start - Info bot\n"
                "5. /help - Bantuan ini",
                thread_id)
            return {"ok": True}

        if text.lower().startswith('/cek'):
            m = re.search(r'@([A-Za-z0-9_]+)', text)
            uname = None
            if m:
                uname = m.group(1).lower()
            else:
                parts = text.split()
                if len(parts) > 1:
                    uname = parts[1].lower().replace('@','').strip()
            
            if not uname:
                send_message(chat_id, "❓ Format: /cek @username", thread_id)
                return {"ok": True}

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT nama, cabang, created_at FROM verifikasi_list WHERE username=%s", (uname,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                send_message(chat_id, f"✅ <b>Ketemu!</b>\n\nNama: {row[0]}\nUsername: @{uname}\nCabang: {row[1]}\nTanggal: {row[2]}", thread_id)
            else:
                send_message(chat_id, f"❌ @{uname} belum ada di database", thread_id)
            return {"ok": True}

        if text.lower().startswith('/hapus'):
            m = re.search(r'@([A-Za-z0-9_]+)', text)
            uname = None
            if m:
                uname = m.group(1).lower()
            else:
                parts = text.split()
                if len(parts) > 1:
                    uname = parts[1].lower().replace('@','').strip()
            
            if not uname:
                send_message(chat_id, "❓ Format: /hapus @username", thread_id)
                return {"ok": True}

            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM verifikasi_list WHERE username=%s", (uname,))
            conn.commit()
            cur.close()
            conn.close()
            send_message(chat_id, f"🗑️ Data @{uname} dihapus!", thread_id)
            return {"ok": True}

        if 'Nama:' in text and 'Username:' in text:
            nama = re.search(r'Nama:\s*(.*)', text, re.I)
            username = re.search(r'Username:\s*@?(\S+)', text, re.I)
            cabang = re.search(r'Cabang:\s*(.*)', text, re.I)
            if nama and username:
                uname = username.group(1).lower().strip('@ ,')
                conn = get_db()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO verifikasi_list (username, nama, cabang)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (username) DO UPDATE SET nama=%s, cabang=%s
                """, (uname, nama.group(1).strip(), cabang.group(1).strip() if cabang else '-', nama.group(1).strip(), cabang.group(1).strip() if cabang else '-'))
                conn.commit()
                cur.close()
                conn.close()
                send_message(chat_id, f"✅ <b>Berhasil!</b>\n\nNama: {nama.group(1).strip()}\nUsername: @{uname}\nCabang: {cabang.group(1).strip() if cabang else '-'}", thread_id)

        return {"ok": True}
    except Exception as e:
        print("ERROR:", e)
        return {"ok": True}

@app.route('/', methods=['GET'])
def home():
    return "Bot Sync JogjaLend Aktif! v3 FIX"

if __name__ == "__main__":
    app.run()