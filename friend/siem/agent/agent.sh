#!/bin/bash
# SIEM-агент для Astra linux.
# Режимы: normal (каждые 5 мин) | hourly | daily | inventory

set -u

CONF="/opt/siem/agent.conf"
STATE="/var/lib/siem-agent"
LOGFILE="$STATE/agent.log"
MODE="${1:-normal}"

mkdir -p "$STATE"
chmod 700 "$STATE"
[ -f "$CONF" ] && source "$CONF"

log() { echo "$(date -Iseconds) $1" >> "$LOGFILE"; }

# ---------------------------------------------------------------
# event $1=тип $2=серьёзность $3=сообщение $4=(необяз.) JSON-детали
# ---------------------------------------------------------------
event() {
    local TYPE="$1" SEV="$2" MSG="$3" DETAILS="${4:-{}}"
    local TIMESTAMP
    TIMESTAMP="$(date -Iseconds)"

    # Используем python3 для валидной сборки JSON (details через stdin)
    local JSON
    JSON=$(python3 -c "
import sys, json
details_raw = sys.stdin.read().strip()
details = json.loads(details_raw) if details_raw else {}
data = {
    'hostname': sys.argv[1],
    'event_type': sys.argv[2],
    'severity': sys.argv[3],
    'message': sys.argv[4],
    'details': details,
    'occurred_at': sys.argv[5],
}
print(json.dumps(data, ensure_ascii=False))
" "$HOSTNAME" "$TYPE" "$SEV" "$MSG" "$TIMESTAMP" <<< "$DETAILS" 2>/dev/null)

    if [ -n "$JSON" ]; then
        echo "$JSON" | /opt/siem/send.sh
    else
        log "event() failed to build JSON for $TYPE"
    fi
}

# ---------------------------------------------------------------
# parse_logins <кол-во записей>
# Читает last -F, выдаёт строки "user|источник|ISO-дата".
# LC_ALL=C — чтобы даты были на английском и date их разобрал.
# ---------------------------------------------------------------
parse_logins() {
    LC_ALL=C last -F -n "$1" 2>/dev/null \
    | awk '
        $1=="reboot" || $1=="shutdown" || $1=="wtmp" || $1=="" {next}
        {
            user=$1; src=""; f=3;
            if ($3 ~ /^[0-9]+\./) { src=$3; f=4 }
            m=$(f); d=$(f+1); t=$(f+2); y=$(f+3);
            if (m ~ /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)$/)
                printf "%s|%s|%s %s %s %s\n", user, src, m, d, t, y;
        }' \
    | while IFS='|' read -r U SRC DATERAW; do
        ISO=$(date -d "$DATERAW" -Iseconds 2>/dev/null) || continue
        [ -n "$ISO" ] || continue
        printf '%s|%s|%s\n' "$U" "$SRC" "$ISO"
      done
}

# ===============================================================
# БЛОК 1. Неудачные попытки входа по SSH (инкрементально)
# ===============================================================
OFFSET_FILE="$STATE/auth_offset"
LAST_TS=$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)
NOW_TS=$(date +%s)

FAILED=$(journalctl _COMM=sshd --since "@$LAST_TS" --until "@$NOW_TS" 2>/dev/null \
    | grep -iE 'Failed password|Invalid user' | wc -l)

if [ "$FAILED" -ge "${AUTH_FAIL_THRESHOLD:-5}" ]; then
    IPS=$(journalctl _COMM=sshd --since "@$LAST_TS" --until "@$NOW_TS" 2>/dev/null \
        | grep -iE 'Failed password|Invalid user' \
        | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' \
        | sort -u | tr '\n' ',' | sed 's/,$//')
    event auth_failed warning \
        "Неудачных SSH-входов за интервал: $FAILED (IP: $IPS)" \
        "{\"count\": $FAILED, \"sources\": \"$IPS\"}"
    log "auth_failed count=$FAILED ips=$IPS"
fi
echo "$NOW_TS" > "$OFFSET_FILE"

# ===============================================================
# БЛОК 2. Новые входы пользователей (инкрементально, каждые 5 мин)
# Сравниваем по отметке времени последнего обработанного входа.
# Сервер сам проверит, не был ли пользователь в отпуске.
# ===============================================================
LOGIN_OFFSET=$(cat "$STATE/logins_offset" 2>/dev/null || echo "")
SINCE_EPOCH=0
[ -n "$LOGIN_OFFSET" ] && SINCE_EPOCH=$(date -d "$LOGIN_OFFSET" +%s 2>/dev/null || echo 0)

NEW_LOGINS=""
MAX_TS="$SINCE_EPOCH"
while IFS='|' read -r U SRC ISO; do
    TS=$(date -d "$ISO" +%s 2>/dev/null) || continue
    [ -n "$TS" ] || continue
    if [ "$TS" -gt "$SINCE_EPOCH" ]; then
        NEW_LOGINS="$NEW_LOGINS{\"user\": \"$U\", \"source\": \"$SRC\", \"at\": \"$ISO\"},"
    fi
    [ "$TS" -gt "$MAX_TS" ] && MAX_TS=$TS
done < <(parse_logins 30)

if [ -n "$NEW_LOGINS" ]; then
    event login info "Новые входы пользователей" \
        "{\"logins\": [${NEW_LOGINS%,}]}"
    log "new logins sent"
fi
date -Iseconds > "$STATE/logins_offset"

# ===============================================================
# БЛОК 3. Целостность критичных файлов
# ===============================================================
HASH_FILE="$STATE/hashes.new"
for F in /etc/passwd /etc/group /etc/shadow /etc/sudoers /etc/hosts; do
    [ -f "$F" ] || continue
    H=$(sha256sum "$F" 2>/dev/null | cut -d' ' -f1)
    PREV=$(grep " ${F//\//\\/}$" "$STATE/hashes" 2>/dev/null | cut -d' ' -f1)
    if [ -n "$PREV" ] && [ "$PREV" != "$H" ]; then
        event file_changed critical "Изменён критичный файл: $F" "{\"file\": \"$F\"}"
        log "file_changed $F"
    fi
    echo "$H $F" >> "$HASH_FILE"
done
mv "$HASH_FILE" "$STATE/hashes"

# ===============================================================
# БЛОК 4. Пользователи с UID 0
# ===============================================================
UID0_CURRENT=$(awk -F: '$3 == 0 {print $1}' /etc/passwd | tr '\n' ',' | sed 's/,$//')
UID0_PREV=$(cat "$STATE/uid0" 2>/dev/null || echo "root")
if [ "$UID0_CURRENT" != "$UID0_PREV" ] && [ -n "$UID0_PREV" ]; then
    event uid0_added critical \
        "Список пользователей с UID 0 изменился: было [$UID0_PREV], стало [$UID0_CURRENT]" \
        "{\"prev\": \"$UID0_PREV\", \"current\": \"$UID0_CURRENT\"}"
fi
echo "$UID0_CURRENT" > "$STATE/uid0"

# ===============================================================
# БЛОК 5. Heartbeat
# ===============================================================
event agent_alive info "Агент работает"

# ===============================================================
# РЕЖИМ hourly
# ===============================================================
if [ "$MODE" = "hourly" ]; then
    PORTS_CURRENT=$(ss -tulpn 2>/dev/null | awk 'NR>1 {print $5}' | sort -u | tr '\n' ';' | sed 's/;$//')
    PORTS_PREV=$(cat "$STATE/ports" 2>/dev/null || echo "")
    if [ -n "$PORTS_PREV" ] && [ "$PORTS_CURRENT" != "$PORTS_PREV" ]; then
        event new_port warning "Набор открытых портов изменился" \
            "{\"prev\": \"$PORTS_PREV\", \"current\": \"$PORTS_CURRENT\"}"
    fi
    echo "$PORTS_CURRENT" > "$STATE/ports"

    USED=$(df --output=pcent / | tail -1 | tr -dc '0-9')
    if [ -n "$USED" ] && [ "$USED" -ge "${DISK_THRESHOLD:-90}" ]; then
        event disk_full warning "Корневой раздел заполнен на $USED%" "{\"used_pct\": $USED}"
    fi

    CRON_CURRENT=$(ls -la /etc/cron.d/ /etc/crontab 2>/dev/null | sha256sum | cut -d' ' -f1)
    CRON_PREV=$(cat "$STATE/cron_hash" 2>/dev/null || echo "")
    if [ -n "$CRON_PREV" ] && [ "$CRON_CURRENT" != "$CRON_PREV" ]; then
        event cron_changed warning "Список задач cron изменился"
    fi
    echo "$CRON_CURRENT" > "$STATE/cron_hash"
fi

# ===============================================================
# РЕЖИМ daily: история входов за месяц + пакеты к обновлению
# ===============================================================
if [ "$MODE" = "daily" ]; then
    # --- Входы за 30 дней ---
    CUT_EPOCH=$(( $(date +%s) - 30*24*3600 ))
    N=0
    LOGINS_JSON=""
    while IFS='|' read -r U SRC ISO; do
        TS=$(date -d "$ISO" +%s 2>/dev/null) || continue
        [ -n "$TS" ] || continue
        [ "$TS" -ge "$CUT_EPOCH" ] || continue
        LOGINS_JSON="$LOGINS_JSON{\"user\": \"$U\", \"source\": \"$SRC\", \"at\": \"$ISO\"},"
        N=$((N+1))
    done < <(parse_logins 2000)

    if [ "$N" -gt 0 ]; then
        event logins_month info "История входов за 30 дней: $N записей" \
            "{\"logins\": [${LOGINS_JSON%,}]}"
        log "logins_month sent: $N"
    fi

    # --- Пакеты, требующие обновления ---
    UPD=$(apt list --upgradable 2>/dev/null | tail -n +2 | grep -v '^$')
    UPD_COUNT=$(printf '%s' "$UPD" | grep -c .)
    if [ "$UPD_COUNT" -gt 0 ]; then
        NAMES=$(printf '%s' "$UPD" | head -15 | awk -F/ '{print $1}' | tr '\n' ',' | sed 's/,$//')
        event updates_pending info "Требуют обновления: $UPD_COUNT пакетов" \
            "{\"count\": $UPD_COUNT, \"packages\": \"$NAMES\"}"
        log "updates_pending: $UPD_COUNT"
    fi
fi

# ===============================================================
# РЕЖИМ inventory: расширенный инвентарь (раз в сутки)
# ===============================================================
if [ "$MODE" = "inventory" ]; then
    SERIAL=$(dmidecode -s system-serial-number 2>/dev/null)
    MODEL=$(dmidecode -s system-product-name 2>/dev/null)
    OS_NAME=$(grep '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' || hostnamectl | grep 'Operating System' | cut -d: -f2 | xargs)
    OS=$(cat /etc/astra_version 2>/dev/null || echo "")
    KERNEL=$(uname -r)
    CPU=$(lscpu | grep 'Model name' | cut -d: -f2 | xargs)
    RAM=$(free -m | awk '/Mem:/{print $2}')
    PKGS=$(dpkg -l 2>/dev/null | grep -c '^ii')
    SUID_COUNT=$(find / -perm -4000 -type f 2>/dev/null | wc -l)

    # IP-адреса
    IP_ALL=$(hostname -I 2>/dev/null | xargs)

    # Дата установки ОС (по дате создания корневой файловой системы)
    FS=$(findmnt -n -o SOURCE / 2>/dev/null | head -1)
    [ -z "$FS" ] && FS=$(df --output=source / | tail -1)
    INSTALL_DATE=$(tune2fs -l "$FS" 2>/dev/null | awk -F': *' '/Filesystem created/{print $2}')
    [ -z "$INSTALL_DATE" ] && INSTALL_DATE=$(stat -c '%w' / 2>/dev/null)

    # Антивирус: ищем известные процессы, версию и дату обновления
    AV=""
    AV_VERSION=""
    AV_UPDATE=""
    for P in kesl drweb-esd drwebd clamd kavesrv; do
        pgrep -x "$P" >/dev/null 2>&1 && AV="$AV $P"
    done
    AV=$(echo "$AV" | xargs)

    if [ -n "$AV" ]; then
        # Касперский (KESL)
        if pgrep -x kesl >/dev/null 2>&1; then
            AV_VERSION=$(kesl-config --get-version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            [ -z "$AV_VERSION" ] && AV_VERSION=$(dpkg -l kaspersky* 2>/dev/null | awk '/^ii/{print $3; exit}')
            # Дата обновления баз
            AV_UPDATE=$(find /opt/kaspersky/kesl/scanner/var/ -name "*.db" -printf '%T@\n' 2>/dev/null | sort -rn | head -1 | xargs -I{} date -d @{} '+%Y-%m-%d %H:%M' 2>/dev/null)
            [ -z "$AV_UPDATE" ] && AV_UPDATE=$(ls -lt /opt/kaspersky/kesl/scanner/var/*.db 2>/dev/null | head -1 | awk '{print $6, $7, $8}')
        # Drweb
        elif pgrep -x drweb-esd >/dev/null 2>&1 || pgrep -x drwebd >/dev/null 2>&1; then
            AV_VERSION=$(drweb-config --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1)
            [ -z "$AV_VERSION" ] && AV_VERSION=$(dpkg -l drweb* 2>/dev/null | awk '/^ii/{print $3; exit}')
            AV_UPDATE=$(ls -lt /opt/drweb/update/*.db 2>/dev/null | head -1 | awk '{print $6, $7, $8}')
        # ClamAV
        elif pgrep -x clamd >/dev/null 2>&1; then
            AV_VERSION=$(clamd --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
            AV_UPDATE=$(ls -lt /var/lib/clamav/*.cld 2>/dev/null | head -1 | awk '{print $6, $7, $8}')
        fi
        [ -z "$AV_UPDATE" ] && AV_UPDATE="не определена"
    fi

    # Температура CPU: max из всех thermal_zone (милиградусы -> градусы)
    TEMP_RAW=$(for Z in /sys/class/thermal/thermal_zone*; do
        cat "$Z/temp" 2>/dev/null; done | sort -rn | head -1)
    TEMP_C=""
    [ -n "$TEMP_RAW" ] && TEMP_C=$((TEMP_RAW/1000))
    if command -v sensors >/dev/null 2>&1; then
        SENS=$(sensors 2>/dev/null | awk '/Package id 0|Core 0|Tctl/{gsub("[+°C]","",$NF); print $NF; exit}')
        [ -n "$SENS" ] && TEMP_C="$SENS"
    fi

    # Таймаут блокировки экрана (best effort, см. примечание ниже)
    CONSOLE_USER=$(who | awk '/:[0-9]/{print $1; exit}')
    LOCK_INFO=""
    LOCK_TIMEOUT=""
    if [ -n "$CONSOLE_USER" ]; then
        LOCK_INFO=$(sudo -u "$CONSOLE_USER" env DISPLAY=:0 xset q 2>/dev/null \
            | grep -A2 'Screen Saver' | grep -oE 'timeout:[[:space:]]+[0-9]+' | head -1)
        if [ -n "$LOCK_INFO" ]; then
            LOCK_TIMEOUT=$(echo "$LOCK_INFO" | grep -oE '[0-9]+')
        fi
    fi
    # Fallback: проверяем gsettings / dconf
    if [ -z "$LOCK_TIMEOUT" ] && command -v gsettings >/dev/null 2>&1; then
        LOCK_TIMEOUT=$(sudo -u "$CONSOLE_USER" env DISPLAY=:0 gsettings get org.gnome.desktop.session screen-delay 2>/dev/null | tr -dc '0-9')
    fi
    if [ -z "$LOCK_TIMEOUT" ] && [ -n "$LOCK_INFO" ]; then
        LOCK_TIMEOUT=$(echo "$LOCK_INFO" | grep -oE '[0-9]+')
    fi

    # Диски: список дисков с размерами
    DISK_INFO=$(lsblk -d -n -o NAME,SIZE,TYPE,MODEL 2>/dev/null | awk '{printf "%s:%s:%s:%s ", $1, $2, $3, $4}' | sed 's/ $//')
    DISK_COUNT=$(lsblk -d -n -o TYPE 2>/dev/null | grep -c 'disk')

    # Пользователи онлайн (список)
    USERS_ONLINE=$(who 2>/dev/null | wc -l)
    USERS_LIST=$(who 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ',' | sed 's/,$//')
    [ -z "$USERS_LIST" ] && USERS_LIST=""

    # Root login (SSH)
    PERMIT_ROOT=$(grep -E '^PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' | head -1)
    [ -z "$PERMIT_ROOT" ] && PERMIT_ROOT=$(grep -E '^PermitRootLogin' /etc/ssh/sshd_config.d/*.conf 2>/dev/null | awk '{print $2}' | head -1)
    [ -z "$PERMIT_ROOT" ] && PERMIT_ROOT="не найдено"

    # Мин. длина пароля (PAM)
    PASS_MIN_LEN=$(grep -E '^pass_min_len' /etc/security/pam_pwquality.conf 2>/dev/null | cut -d= -f2 | xargs)
    [ -z "$PASS_MIN_LEN" ] && PASS_MIN_LEN=$(grep -E '^minlen' /etc/pam.d/common-password 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /minlen/) print $(i+1)}' | head -1)
    [ -z "$PASS_MIN_LEN" ] && PASS_MIN_LEN=$(grep -E '^PASS_MIN_LEN' /etc/login.defs 2>/dev/null | awk '{print $2}')
    [ -z "$PASS_MIN_LEN" ] && PASS_MIN_LEN="0"

    # Загрузка системы (load average 1, 5, 15 мин)
    LOAD_AVG=$(cat /proc/loadavg 2>/dev/null | awk '{print $1", "$2", "$3}')
    [ -z "$LOAD_AVG" ] && LOAD_AVG="—"

    # Uptime
    UPTIME_RAW=$(uptime 2>/dev/null | sed 's/.*up\s*//' | sed 's/\s*user.*//')
    UPTIME_HOURS=$(awk '{print $1}' /proc/uptime 2>/dev/null)
    if [ -n "$UPTIME_HOURS" ]; then
        # Конвертируем float в int (убираем десятичную часть)
        UPTIME_HOURS_INT=$(echo "$UPTIME_HOURS" | awk '{printf "%d", $1}')
        UPTIME_DAYS=$((UPTIME_HOURS_INT / 86400))
        UPTIME_REST=$((UPTIME_HOURS_INT % 86400))
        UPTIME_HOURS_SHORT=$((UPTIME_REST / 3600))
        UPTIME_MINS=$(( (UPTIME_REST % 3600) / 60 ))
        UPTIME_DISPLAY=""
        [ "$UPTIME_DAYS" -gt 0 ] && UPTIME_DISPLAY="${UPTIME_DAYS} дн. "
        UPTIME_DISPLAY="${UPTIME_DISPLAY}${UPTIME_HOURS_SHORT} ч. ${UPTIME_MINS} мин."
    else
        UPTIME_DISPLAY="—"
    fi

    # Формируем users_list как JSON-массив строк
    USERS_JSON="["
    FIRST=true
    for U in $(who 2>/dev/null | awk '{print $1}' | sort -u); do
        [ "$FIRST" = true ] && FIRST=false || USERS_JSON="$USERS_JSON, "
        USERS_JSON="$USERS_JSON\"$U\""
    done
    USERS_JSON="$USERS_JSON]"
    if [ -z "$USERS_JSON" ] || [ "$USERS_JSON" = "[]" ]; then
        USERS_JSON="[]"
    fi

    # --- История браузеров (Chrome/Chromium/Firefox) через python3 ---
    BROWSER_JSON="[]"
    BROWSER_COUNT=0
    
    log "browser_history: starting scan..."
    
    # Собираем пути к базам браузеров
    BROWSER_DBS=""
    for DB in ~/.config/google-chrome/Default/History ~/.config/chromium/Default/History ~/.local/share/containersbox/Default/History; do
        [ -f "$DB" ] && BROWSER_DBS="$BROWSER_DBS chrome:$DB"
    done
    for DB in ~/.mozilla/firefox/*.default*/places.sqlite ~/.mozilla/firefox/*.default*/places.sqlite-old; do
        [ -f "$DB" ] && BROWSER_DBS="$BROWSER_DBS firefox:$DB"
    done
    
    log "browser_history: DBs=$BROWSER_DBS"
    
    if [ -n "$BROWSER_DBS" ]; then
        # Используем python3 с встроенным sqlite3
        BROWSER_JSON=$(python3 -c "
import sqlite3, json, sys, os, glob

browser_dbs = '$BROWSER_DBS'.split()
urls = []

for db_spec in browser_dbs:
    parts = db_spec.split(':', 1)
    if len(parts) != 2:
        continue
    db_type, db_path = parts
    if not os.path.isfile(db_path):
        continue
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        if db_type == 'chrome':
            # Chrome/Chromium
            cur.execute('''
                SELECT u.url, u.title, datetime(v.visit_time/1000000+11644473600, 'unixepoch', 'localtime')
                FROM visits v
                INNER JOIN urls u ON v.url = u.id
                ORDER BY v.visit_time DESC
                LIMIT 200
            ''')
        elif db_type == 'firefox':
            # Firefox
            cur.execute('''
                SELECT p.url, p.title, datetime(p.last_visit_date/1000000, 'unixepoch', 'localtime')
                FROM moz_places p
                WHERE p.url NOT LIKE 'moz%' AND p.url NOT LIKE 'chrome%'
                ORDER BY p.last_visit_date DESC
                LIMIT 200
            ''')
        
        for row in cur.fetchall():
            url, title, visited = row
            if url:
                urls.append({'url': url or '', 'title': title or '', 'visited': visited or ''})
        
        conn.close()
        print(f'[OK] {db_path}: {len(urls)} URLs total', file=sys.stderr)
    except Exception as e:
        print(f'[ERROR] {db_path}: {e}', file=sys.stderr)

# Сортируем по времени посещения (новые первые)
urls.sort(key=lambda x: x.get('visited', ''), reverse=True)
# Ограничиваем 200 записями
urls = urls[:200]
print(json.dumps(urls, ensure_ascii=False))
" 2>/dev/null)
        
        # Считаем количество
        if [ -n "$BROWSER_JSON" ]; then
            BROWSER_COUNT=$(echo "$BROWSER_JSON" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read())))" 2>/dev/null || echo 0)
        fi
        
        log "browser_history: count=$BROWSER_COUNT"
    fi

    if [ "$BROWSER_COUNT" -gt 0 ]; then
        # Отправляем напрямую через curl (event() не может встроить большой JSON)
        TIMESTAMP="$(date -Iseconds)"
        BROWSER_PAYLOAD=$(python3 -c "
import sys, json
hostname = sys.argv[1]
timestamp = sys.argv[2]
count = int(sys.argv[3])
# Читаем JSON из stdin
urls_json = sys.stdin.read().strip()
data = {
    'hostname': hostname,
    'event_type': 'browser_history',
    'severity': 'info',
    'message': f'История браузеров: {count} записей',
    'details': {'count': count, 'urls': json.loads(urls_json)},
    'occurred_at': timestamp,
}
print(json.dumps(data, ensure_ascii=False))
" "$HOSTNAME" "$TIMESTAMP" "$BROWSER_COUNT" <<< "$BROWSER_JSON" 2>/dev/null)
        
        if [ -n "$BROWSER_PAYLOAD" ]; then
            RESPONSE=$(curl -s --max-time "${CURL_TIMEOUT:-10}" -X POST "${SERVER}/api/siem/ingest/" \
                -H "Content-Type: application/json" \
                -H "Authorization: Token ${TOKEN}" \
                -d "$BROWSER_PAYLOAD" 2>&1)
            log "browser_history: sent $BROWSER_COUNT URLs, response=$RESPONSE"
        else
            log "browser_history: ERROR - failed to build payload"
        fi
    else
        log "browser_history: no URLs found"
    fi

    event inventory info "Инвентаризация выполнена" \
        "{\"serial\": \"$SERIAL\", \"model\": \"$MODEL\", \"os\": \"$OS\", \"os_name\": \"$OS_NAME\",
          \"kernel\": \"$KERNEL\", \"cpu\": \"$CPU\", \"ram_mb\": $RAM,
          \"packages\": $PKGS, \"suid_count\": $SUID_COUNT,
          \"install_date\": \"$INSTALL_DATE\", \"ip\": \"$IP_ALL\",
          \"antivirus\": \"$AV\", \"av_version\": \"$AV_VERSION\",
          \"av_update\": \"$AV_UPDATE\", \"temp_c\": \"$TEMP_C\",
          \"lock_info\": \"$LOCK_INFO\", \"lock_timeout\": $LOCK_TIMEOUT,
          \"users_online\": $USERS_ONLINE, \"users_list\": $USERS_JSON,
          \"permit_root_login\": \"$PERMIT_ROOT\",
          \"pass_min_len\": $PASS_MIN_LEN,
          \"load_avg\": \"$LOAD_AVG\", \"uptime_hours\": $UPTIME_HOURS_INT,
          \"uptime_display\": \"$UPTIME_DISPLAY\"}"

    # Снимок для вкладки «Инвентаризация»
    # Формируем disk_info как JSON-массив из lsblk
    DISK_JSON="["
    FIRST=true
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        D_NAME=$(echo "$line" | awk '{print $1}')
        D_SIZE=$(echo "$line" | awk '{print $2}')
        D_TYPE=$(echo "$line" | awk '{print $3}')
        D_MODEL=$(echo "$line" | awk '{$1=""; $2=""; $3=""; print}' | xargs)
        [ "$FIRST" = true ] && FIRST=false || DISK_JSON="$DISK_JSON, "
        DISK_JSON="$DISK_JSON{\"name\": \"$D_NAME\", \"size\": \"$D_SIZE\", \"type\": \"$D_TYPE\", \"model\": \"$D_MODEL\"}"
    done < <(lsblk -d -n -o NAME,SIZE,TYPE,MODEL 2>/dev/null)
    DISK_JSON="$DISK_JSON]"
    [ -z "$DISK_JSON" ] || [ "$DISK_JSON" = "[]" ] && DISK_JSON="[]"

    INVENTORY_PAYLOAD=$(printf '{
        "hostname": "%s",
        "cpu_model": "%s",
        "ram_mb": %s,
        "packages_count": %s,
        "open_ports": [],
        "disk_info": %s,
        "raw": {
            "serial": "%s", "model": "%s", "os": "%s", "os_name": "%s", "kernel": "%s",
            "install_date": "%s", "ip": "%s", "antivirus": "%s",
            "av_version": "%s", "av_update": "%s",
            "temp_c": "%s", "lock_info": "%s", "lock_timeout": "%s",
            "users_online": %s, "users_list": %s,
            "permit_root_login": "%s", "pass_min_len": "%s",
            "suid_count": %s, "load_avg": "%s",
            "uptime_hours": %s, "uptime_display": "%s",
            "agent_version": "1.1"
        }
    }' "$HOSTNAME" "$CPU" "$RAM" "$PKGS" "$DISK_JSON" "$SERIAL" "$MODEL" "$OS" "$OS_NAME" "$KERNEL" \
       "$INSTALL_DATE" "$IP_ALL" "$AV" "$AV_VERSION" "$AV_UPDATE" "$TEMP_C" "$LOCK_INFO" "$LOCK_TIMEOUT" "$USERS_ONLINE" "$USERS_JSON" "$PERMIT_ROOT" "$PASS_MIN_LEN" "$SUID_COUNT" "$LOAD_AVG" "$UPTIME_HOURS_INT" "$UPTIME_DISPLAY")

    curl -s --max-time "${CURL_TIMEOUT:-10}" -X POST "$SERVER/api/siem/ingest/inventory/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Token $TOKEN" \
        -d "$INVENTORY_PAYLOAD" > /dev/null 2>&1

    log "inventory done: serial=$SERIAL temp=$TEMP_C av=$AV"
fi

exit 0
