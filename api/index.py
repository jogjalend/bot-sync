from flask import Flask, request
import os, psycopg2, re, requests

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
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
            job TEXT,
            spek TEXT,
            cabang TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    # Tambah kolom baru kalau belum ada
    cur.execute("ALTER TABLE verifikasi_list ADD COLUMN IF NOT EXISTS job TEXT")
    cur.execute("ALTER TABLE verifikasi_list ADD COLUMN IF NOT EXISTS spek TEXT")
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
                "Format baru:\n"
                "Nama : Nadyn\n"
                "Username : @nadynxyz\n"
                "Job : Designer\n"
                "Spek : Laptop\n\n"
                "Ketik /help",
                thread_id)
            return {"ok": True}

        if text.startswith('/help'):
            send_message(chat_id,
                "📖 <b>Format Baru:</b>\n\n"
                "Nama : Budi\n"
                "Username : @budi\n"
                "Job : Programmer\n"
                "Spek : PC High\n\n"
                "Perintah:\n"
                "/cek @username\n"
                "/hapus @username\n"
                "/start",
                thread_id)
            return {"ok": True}

        if text.lower().startswith('/cek'):
            m = re.search(r'@([A-Za-z0-9_]+)', text)
            uname = m.group(1).lower() if m else (text.split()[1].lower().replace('@','') if len(text.split())>1 else None)
            if not uname:
                send_message(chat_id, "❓ Format: /cek @username", thread_id)
                return {"ok": True}
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT nama, job, spek FROM verifikasi_list WHERE username=%s", (uname,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                send_message(chat_id, f"✅ <b>Ketemu!</b>\n\nNama: {row[0]}\nUsername: @{uname}\nJob: {row[1]}\nSpek: {row[2]}", thread_id)
            else:
                send_message(chat_id, f"❌ @{uname} belum ada", thread_id)
            return {"ok": True}

        if text.lower().startswith('/hapus'):
            m = re.search(r'@([A-Za-z0-9_]+)', text)
            uname = m.group(1).lower() if m else (text.split()[1].lower().replace('@','') if len(text.split())>1 else None)
            if not uname:
                send_message(chat_id, "❓ Format: /hapus @username", thread_id)
                return {"ok": True}
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM verifikasi_list WHERE username=%s", (uname,))
            conn.commit()
            cur.close()
            conn.close()
            send_message(chat_id, f"🗑️ @{uname} dihapus!", thread_id)
            return {"ok": True}

        # FORMAT BARU: Nama: Username: Job: Spek:
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
                send_message(chat_id, f"✅ <b>Berhasil!</b>\n\nNama: {nama.group(1).strip()}\nUsername: @{uname}\nJob: {job.group(1).strip() if job else '-'}\nSpek: {spek.group(1).strip() if spek else '-'}", thread_id)

        return {"ok": True}
    except Exception as e:
        print("ERROR:", e)
        return {"ok": True}

@app.route('/', methods=['GET'])
def home():
    return "Bot Sync v4 Format Baru"

if __name__ == "__main__":
    app.run()