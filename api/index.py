from flask import Flask, request
import os, requests, re, json
from datetime import datetime

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GROUP_ID = os.getenv("JOGJALEND_GROUP_ID") or os.getenv("MAIN_GROUP_ID") or ""
THREAD_ID = int(os.getenv("VERIF_THREAD_ID", "54"))

try:
    import psycopg2
    HAS_PG = True
except:
    HAS_PG = False

def pg_conn():
    if not DATABASE_URL or not HAS_PG: return None
    try: return psycopg2.connect(DATABASE_URL)
    except: return None

def pg_init():
    conn = pg_conn()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verifikasi_list (
                user_id TEXT,
                username TEXT,
                name TEXT,
                verified_at TIMESTAMP DEFAULT NOW(),
                source_msg_id TEXT,
                PRIMARY KEY (user_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verifikasi_username (
                username TEXT PRIMARY KEY,
                user_id TEXT,
                verified_at TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit(); cur.close(); conn.close()
        print("Neon verif table ready")
    except Exception as e:
        print(f"Init error {e}")

pg_init()

def add_verif(user_id, username, name, msg_id):
    conn = pg_conn()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO verifikasi_list (user_id, username, name, source_msg_id)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (user_id) DO UPDATE SET username=%s, name=%s, verified_at=NOW();
        """, (str(user_id), username, name, str(msg_id), username, name))
        if username:
            cur.execute("""
                INSERT INTO verifikasi_username (username, user_id)
                VALUES (%s,%s)
                ON CONFLICT (username) DO UPDATE SET user_id=%s, verified_at=NOW();
            """, (username.lower(), str(user_id), str(user_id)))
        conn.commit(); cur.close(); conn.close()
        return True
    except Exception as e:
        print(f"add_verif error {e}")
        return False

def is_verified(user_id, username):
    conn = pg_conn()
    if not conn: return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM verifikasi_list WHERE user_id=%s;", (str(user_id),))
        if cur.fetchone():
            cur.close(); conn.close(); return True
        if username:
            cur.execute("SELECT 1 FROM verifikasi_username WHERE username=%s;", (username.lower(),))
            if cur.fetchone():
                cur.close(); conn.close(); return True
        cur.close(); conn.close()
        return False
    except: return False

def parse_verif_message(text, entities=None):
    # Format yang didukung di Topic 54:
    # @username udah verif
    # ID: 123456789 Nama: Jogja Lend
    # atau forward kontak / user id
    results = []
    if not text: return results
    # cari @username
    usernames = re.findall(r'@([a-zA-Z0-9_]{5,32})', text)
    for u in usernames:
        results.append({"user_id": f"@{u}", "username": u, "name": u})
    # cari angka ID telegram 7-10 digit
    ids = re.findall(r'\b(\d{7,11})\b', text)
    for i in ids:
        results.append({"user_id": i, "username": "", "name": f"User {i}"})
    return results

def send(chat_id, text, thread_id=None, kb=None):
    p={"chat_id": int(chat_id), "text": text, "parse_mode":"HTML"}
    if thread_id: p["message_thread_id"]=thread_id
    if kb: p["reply_markup"]=kb
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=p, timeout=5)
    except: pass

def delete_msg(chat_id, msg_id):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage", json={"chat_id": int(chat_id), "message_id": msg_id}, timeout=3)
    except: pass

@app.route("/", methods=["GET","POST"])
@app.route("/api/index", methods=["GET","POST"])
def index():
    if request.method=="GET":
        return f"VERIF SYNC BOT - Thread {THREAD_ID} - Neon {'OK' if HAS_PG else 'NO PG'}",200

    data=request.get_json(force=True, silent=True) or {}
    if "message" not in data: return "ok",200

    msg=data["message"]
    chat_id=str(msg["chat"]["id"])
    thread_id=msg.get("message_thread_id")
    text=msg.get("text","") or msg.get("caption","")
    from_user=msg.get("from",{})
    uid=str(from_user.get("id",""))
    username=from_user.get("username","")

    # === 1. MONITOR TOPIC 54 - AUTO SYNC VERIF ===
    if str(thread_id)==str(THREAD_ID) and chat_id==str(GROUP_ID) or str(thread_id)==str(THREAD_ID):
        # jika ada user di mention atau di forward
        parsed = parse_verif_message(text)
        # jika reply ke user atau forward
        if "reply_to_message" in msg:
            ruser=msg["reply_to_message"].get("from",{})
            parsed.append({"user_id": str(ruser.get("id")), "username": ruser.get("username",""), "name": ruser.get("first_name","")})
        
        for p in parsed:
            real_uid = p["user_id"]
            if real_uid.startswith("@"): continue # skip kalo cuma @username tanpa ID, simpen username aja
            add_verif(real_uid, p["username"], p["name"], msg.get("message_id"))
            send(chat_id, f"✅ Verifikasi tersync: @{p['username'] or p['name']} (ID:{real_uid}) → Neon", thread_id=thread_id)
        
        # simpan username juga kalo cuma @
        for p in parsed:
            if p["user_id"].startswith("@"):
                add_verif(p["user_id"], p["username"], p["name"], msg.get("message_id"))

    # === 2. CEK DI GRUP UTAMA - AUTO DELETE JIKA BELUM VERIF ===
    # hanya cek di luar thread verif, di grup utama
    if thread_id != THREAD_ID and chat_id==str(GROUP_ID):
        # skip admin & bot
        if text.startswith("/cek") or text.startswith("/verif") or text.startswith("/sync"):
            pass # jangan hapus command
        else:
            # cek verif
            if uid and not is_verified(uid, username):
                # jangan langsung kick, mute + warning dulu
                # delete_msg(chat_id, msg.get("message_id"))
                send(chat_id, f"⚠️ @{username or from_user.get('first_name')} belum terverifikasi di Topic 54!\nSilakan verifikasi dulu di https://t.me/c/xxx/{THREAD_ID}\nPesan kamu akan dihapus jika belum verif.", thread_id=thread_id)

    # === 3. COMMANDS ===
    if text.startswith("/cek"):
        target = text.split("@")[-1].split()[0] if "@" in text else ""
        if "reply_to_message" in msg:
            tuser=msg["reply_to_message"]["from"]
            target_id=str(tuser["id"]); target_un=tuser.get("username","")
            ver = is_verified(target_id, target_un)
            send(chat_id, f"{'✅ SUDAH' if ver else '❌ BELUM'} Verifikasi\nID: {target_id}\nUsername: @{target_un}\nNama: {tuser.get('first_name')}", thread_id=thread_id)
        elif target:
            ver = is_verified("", target)
            send(chat_id, f"{'✅ SUDAH' if ver else '❌ BELUM'} Verifikasi\nUsername: @{target}", thread_id=thread_id)
        else:
            ver = is_verified(uid, username)
            send(chat_id, f"Kamu {'✅ SUDAH' if ver else '❌ BELUM'} Verifikasi\nID: {uid}\nUsername: @{username}", thread_id=thread_id)

    if text.startswith("/verif") and msg.get("from",{}).get("id"):
        # hanya admin bisa manual verif
        try:
            r=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember", params={"chat_id": chat_id, "user_id": msg["from"]["id"]}, timeout=3).json()
            is_adm=r.get("result",{}).get("status") in ["administrator","creator"]
        except: is_adm=False
        if is_adm:
            if "reply_to_message" in msg:
                tuser=msg["reply_to_message"]["from"]
                add_verif(str(tuser["id"]), tuser.get("username",""), tuser.get("first_name",""), msg.get("message_id"))
                send(chat_id, f"✅ Manual Verif: @{tuser.get('username')} ID {tuser['id']} → Neon", thread_id=thread_id)

    if text.startswith("/syncstat"):
        conn=pg_conn()
        if conn:
            cur=conn.cursor()
            cur.execute("SELECT COUNT(*) FROM verifikasi_list;")
            cnt=cur.fetchone()[0]
            cur.close(); conn.close()
            send(chat_id, f"📊 Total terverifikasi di Neon: {cnt}\nSync dari Topic {THREAD_ID}", thread_id=thread_id)

    return "ok",200