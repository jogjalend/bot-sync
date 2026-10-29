from flask import Flask, request
import os, psycopg2, re, requests

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# TOPIC YANG DIJAGA - kalo belum verif, auto delete
PROTECTED_TOPICS = [7245, 1328, 6848, 413, 4, 1745, 4843, 5250, 410]
VERIF_TOPIC = 54

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

def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    payload = {"chat_id": chat_id, "message_id": message_id}
    requests.post(url, json=payload)

def is_verified(username):
    if not username:
        return False
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM verifikasi_list WHERE username=%s", (username.lower(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return bool(row)

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
        sender_username = sender.get('username','').lower()
        sender_id = sender.get('id')

        # === FITUR COMMAND ===
        if text.startswith('/start'):
            send_message(chat_id, "👋 <b>Bot Sync Aktif v5 Auto-Delete!</b>\n\nFormat:\nNama :\nUsername :\nJob :\nSpek :\n\n/cek @user\n/hapus @user\n/help", thread_id)
            return {"ok": True}

        if text.startswith('/help'):
            send_message(chat_id, "📖 <b>Format:</b>\nNama : Budi\nUsername : @budi\nJob : Programmer\nSpek : PC\n\n<b>Perintah:</b>\n/cek @username\n/hapus @username\n\n<b>Protected Topic:</b>\n7245,1328,6848,413,4,1745,4843,5250,410\nAuto delete jika belum verif!", thread_id)
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
            if not uname:
                send_message(chat_id, "❓ /hapus @username", thread_id)
                return {"ok": True}
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM verifikasi_list WHERE username=%s", (uname,))
            conn.commit()
            cur.close()
            conn.close()
            send_message(chat_id, f"🗑️ @{uname} dihapus!", thread_id)
            return {"ok": True}

        # === INPUT DATA VERIFIKASI (DI TOPIC 54) ===
        if 'Nama' in text and 'Username' in text:
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
                send_message(chat_id, f"✅ <b>Berhasil Verif!</b>\nNama: {nama.group(1).strip()}\nUsername: @{uname}\nJob: {job.group(1).strip() if job else '-'}\nSpek: {spek.group(1).strip() if spek else '-'}", thread_id)
                return {"ok": True}

        # === AUTO DELETE LOGIC ===
        # Cek apakah chat ini di topic protected?
        if thread_id in PROTECTED_TOPICS:
            # Jangan delete command dan bot sendiri
            if text.startswith('/'):
                return {"ok": True}
            
            # Cek apakah user sudah verif?
            if not is_verified(sender_username):
                # Hapus pesan
                delete_message(chat_id, message_id)
                # Kirim warning 5 detik lalu hapus? Kita kirim warning aja
                send_message(chat_id, f"⛔ @{sender_username} <b>pesan dihapus!</b>\nBelum masuk list verifikasi.\n\nSilakan verif dulu di topic 54 dengan format:\nNama :\nUsername :\nJob :\nSpek :", thread_id)
                return {"ok": True}

        return {"ok": True}
    except Exception as e:
        print("ERROR:", e)
        return {"ok": True}

@app.route('/', methods=['GET'])
def home():
    return "Bot Sync v5 Auto-Delete Aktif"

if __name__ == "__main__":
    app.run()