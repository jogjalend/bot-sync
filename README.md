# bot-sync - JogjaLend Verif Checker

Bot khusus buat ngecek & sync verifikasi member JogjaLend dari Topic 54 langsung ke Neon DB.

Link Topic Verif: https://t.me/JogjaLend/54

## Fitur Utama
- **Auto Sync**: Tiap ada yang post @username / ID di Topic 54, otomatis kesimpen permanen di Neon
- **Auto Guard**: Kalau belum verif chat di grup utama → auto warning / delete
- **Cek Cepat**:
    - `/cek` → cek status lu sendiri
    - `/cek @username` → cek orang lain
    - `/verif` (reply pesan, admin only) → verif manual
    - `/syncstat` → liat total member yang udah keverif

## Database (Neon Postgres)
Auto create 2 table:
- `verifikasi_list` → simpen user_id, username, nama
- `verifikasi_username` → index cepat buat cek @username

Data gak bakal hilang walau Vercel redeploy.

## Cara Deploy di Vercel
1. Buat bot baru di @BotFather
2. Import repo `bot-sync` ini ke Vercel
3. Isi Environment Variables di Vercel:
      - `BOT_TOKEN`
      - `DATABASE_URL`
      - `JOGJALEND_GROUP_ID`
      - `VERIF_THREAD_ID=54`
4. Set Webhook:
   `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<vercel-app>.vercel.app/api/index`
5. Jadikan bot Admin di grup JogjaLend biar bisa baca Topic & hapus pesan

## Format Verifikasi yang kebaca di Topic 54
Bot ngerti format:
- `@username`
- `ID: 123456789`
- Reply / Forward pesan user yang mau diverif

---
Made for JogjaLend Community - bot-sync v1