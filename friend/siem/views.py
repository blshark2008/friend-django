import logging
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Count, Q
from accounts.models import User
from rest_framework import status, viewsets, generics
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)

from .models import Host, SecurityEvent, InventorySnapshot, RecentLogin, ScreenLockLog, EmployeeLeave, AbsenceAlert
from .serializers import (
    SecurityEventSerializer,
    InventorySnapshotSerializer,
    HostSerializer,
    RecentLoginSerializer,
    ExtendedHostInfoSerializer,
)
from django.db import transaction
from django.http import JsonResponse
from accounts.models import User as AccountUser


# ============================================================================
# HTML-страницы
# ============================================================================

def dashboard(request):
    """Главный дашборд SIEM."""
    now = timezone.now()
    day_ago = now - timezone.timedelta(days=1)
    week_ago = now - timezone.timedelta(weeks=1)

    # Хосты
    hosts_total = Host.objects.count()
    hosts_active = Host.objects.filter(is_active=True).count()
    cutoff = timezone.now() - timezone.timedelta(hours=24)
    hosts_offline = Host.objects.filter(last_seen__lt=cutoff).count()

    # События
    events_today = SecurityEvent.objects.filter(occurred_at__gte=day_ago).count()
    events_critical_today = SecurityEvent.objects.filter(
        occurred_at__gte=day_ago, severity='critical'
    ).count()

    # Алерты
    alerts_total = AbsenceAlert.objects.count()
    alerts_unack = AbsenceAlert.objects.filter(is_acknowledged=False).count()

    # По типам за 24ч
    events_by_type = {}
    for et in SecurityEvent.EventType.values:
        label = dict(SecurityEvent.EventType.choices).get(et, et)
        count = SecurityEvent.objects.filter(
            occurred_at__gte=day_ago, event_type=et
        ).count()
        events_by_type[label] = count

    # Последние события
    recent_events = list(
        SecurityEvent.objects.select_related('host')
        .order_by('-occurred_at')[:10]
    )

    # Оффлайн хосты
    offline_hosts = list(
        Host.objects.filter(last_seen__lt=cutoff)
        .order_by('hostname')
    )

    context = {
        'hosts_total': hosts_total,
        'hosts_active': hosts_active,
        'hosts_offline': hosts_offline,
        'events_today': events_today,
        'events_critical_today': events_critical_today,
        'events_by_type': events_by_type,
        'recent_events': recent_events,
        'offline_hosts': offline_hosts,
        'alerts_total': alerts_total,
        'alerts_unack': alerts_unack,
    }
    return render(request, 'siem/dashboard.html', context)


def hosts_list(request):
    """Список хостов."""
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    hosts = Host.objects.all()

    if search:
        hosts = hosts.filter(
            Q(hostname__icontains=search) |
            Q(os_info__icontains=search) |
            Q(os_name__icontains=search) |
            Q(ip_address__icontains=search)
        )

    if status_filter == 'online':
        hosts = hosts.filter(is_active=True)
    elif status_filter == 'offline':
        hosts = hosts.filter(last_seen__lt=cutoff)

    context = {
        'hosts': hosts,
        'search': search,
        'status': status_filter,
    }
    return render(request, 'siem/hosts.html', context)


def events_list(request):
    """Список событий с фильтрацией."""
    search = request.GET.get('search', '')
    severity = request.GET.get('severity', '')
    event_type = request.GET.get('event_type', '')
    days = request.GET.get('days', 14)  # По умолчанию 2 недели

    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 14

    events = SecurityEvent.objects.select_related('host').all()

    if search:
        events = events.filter(
            Q(message__icontains=search) |
            Q(host__hostname__icontains=search)
        )

    if severity:
        events = events.filter(severity=severity)

    if event_type:
        events = events.filter(event_type=event_type)

    cutoff = timezone.now() - timezone.timedelta(days=days)
    events = events.filter(occurred_at__gte=cutoff)

    events = events.order_by('-occurred_at')

    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(events, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'events': page_obj,
        'search': search,
        'severity': severity,
        'event_type': event_type,
        'days': days,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }
    return render(request, 'siem/events.html', context)


def report_security(request):
    """Отчёт по безопасности."""
    from_date = request.GET.get('from', '')
    to_date = request.GET.get('to', '')

    now = timezone.now()
    if from_date:
        start = timezone.datetime.strptime(from_date, '%Y-%m-%d').replace(
            tzinfo=timezone.utc
        )
    else:
        start = now - timezone.timedelta(days=30)

    if to_date:
        end = timezone.datetime.strptime(to_date, '%Y-%m-%d').replace(
            tzinfo=timezone.utc
        ) + timezone.timedelta(days=1)
    else:
        end = now

    events = SecurityEvent.objects.filter(
        occurred_at__gte=start, occurred_at__lt=end
    )

    total_events = events.count()
    critical_events = events.filter(severity='critical').count()
    warning_events = events.filter(severity='warning').count()
    unique_hosts = events.values('host').distinct().count()

    # По типам
    events_by_type = []
    for et in SecurityEvent.EventType.values:
        label = dict(SecurityEvent.EventType.choices).get(et, et)
        count = events.filter(event_type=et).count()
        if count > 0:
            events_by_type.append({'label': label, 'value': et, 'count': count})

    # Топ offending hosts
    top_offending_hosts = list(
        events.values('host__id', 'host__hostname')
        .annotate(
            total=Count('id'),
            critical=Count('id', filter=Q(severity='critical')),
            warning=Count('id', filter=Q(severity='warning')),
        )
        .order_by('-total')[:10]
    )

    # Последние критические
    recent_critical = list(
        events.filter(severity='critical')
        .select_related('host')
        .order_by('-occurred_at')[:20]
    )

    context = {
        'total_events': total_events,
        'critical_events': critical_events,
        'warning_events': warning_events,
        'unique_hosts': unique_hosts,
        'events_by_type': events_by_type,
        'top_offending_hosts': top_offending_hosts,
        'recent_critical': recent_critical,
        'from_date': from_date,
        'to_date': to_date,
    }
    return render(request, 'siem/report_security.html', context)


def report_inventory(request):
    """Отчёт по инвентаризации."""
    hosts = Host.objects.all()
    total_hosts = hosts.count()
    total_snapshots = InventorySnapshot.objects.count()

    # Данные для таблицы
    inventory_data = []
    for host in hosts:
        latest_snapshot = host.snapshots.first()
        if latest_snapshot:
            inventory_data.append({
                'hostname': host.hostname,
                'os_info': host.os_info,
                'cpu_model': latest_snapshot.cpu_model,
                'ram_mb': latest_snapshot.ram_mb,
                'disk_count': len(latest_snapshot.disk_info) if latest_snapshot.disk_info else 0,
                'packages_count': latest_snapshot.packages_count,
                'open_ports_count': len(latest_snapshot.open_ports),
                'last_snapshot_date': latest_snapshot.collected_at,
            })
        else:
            inventory_data.append({
                'hostname': host.hostname,
                'os_info': host.os_info,
                'cpu_model': '',
                'ram_mb': None,
                'disk_count': 0,
                'packages_count': None,
                'open_ports_count': 0,
                'last_snapshot_date': None,
            })

    hosts_with_snapshot = len([d for d in inventory_data if d['last_snapshot_date']])

    context = {
        'total_hosts': total_hosts,
        'hosts_with_snapshot': hosts_with_snapshot,
        'total_snapshots': total_snapshots,
        'inventory_data': inventory_data,
    }
    return render(request, 'siem/report_inventory.html', context)


def report_hosts(request):
    """Отчёт по хостам."""
    hosts = Host.objects.all()
    total_hosts = hosts.count()
    online_hosts = Host.objects.filter(is_active=True).count()
    cutoff = timezone.now() - timezone.timedelta(hours=24)
    offline_hosts = Host.objects.filter(last_seen__lt=cutoff).count()
    total_events = SecurityEvent.objects.count()

    hosts_data = []
    for host in hosts:
        events = host.events.all()
        hosts_data.append({
            'hostname': host.hostname,
            'os_info': host.os_info,
            'ip_address': host.ip_address,
            'is_active': host.is_active,
            'last_seen': host.last_seen,
            'total_events': events.count(),
            'critical_events': events.filter(severity='critical').count(),
            'warning_events': events.filter(severity='warning').count(),
        })

    context = {
        'total_hosts': total_hosts,
        'online_hosts': online_hosts,
        'offline_hosts': offline_hosts,
        'total_events': total_events,
        'hosts_data': hosts_data,
    }
    return render(request, 'siem/report_hosts.html', context)


def event_detail(request, pk):
    """Полная информация о событии."""
    event = get_object_or_404(SecurityEvent, pk=pk)
    
    # События этого же хоста для навигации
    related_events = event.host.events.filter(
        occurred_at__gte=event.occurred_at - timezone.timedelta(hours=1),
        occurred_at__lte=event.occurred_at + timezone.timedelta(hours=1)
    ).order_by('occurred_at')[:20]
    
    # События этого же типа
    similar_events = event.host.events.filter(
        event_type=event.event_type
    ).order_by('-occurred_at')[:10]

    context = {
        'event': event,
        'related_events': related_events,
        'similar_events': similar_events,
    }
    return render(request, 'siem/event_detail.html', context)


def host_detail(request, pk):
    """Полная информация о хосте."""
    host = get_object_or_404(Host, pk=pk)
    
    # Последние события
    recent_events = host.events.select_related().order_by('-occurred_at')[:50]
    
    # Снимки инвентаризации (из API /ingest/inventory/)
    snapshots = host.snapshots.order_by('-collected_at')[:10]
    latest_snapshot = host.snapshots.first()
    
    # Инвентаризация из события agent (MODE=inventory) — legacy
    inventory_event = host.events.filter(event_type='inventory').order_by('-occurred_at').first()
    inventory_details = inventory_event.details if inventory_event else {}
    
    # Raw данные из последнего снимка (IP, антивирус, температура и т.д.)
    raw_data = {}
    if latest_snapshot and latest_snapshot.raw:
        raw_data = latest_snapshot.raw.copy()
        # Парсим ports и services для шаблона
        if 'ports' in raw_data and isinstance(raw_data['ports'], str):
            raw_data['ports_list'] = [p.strip() for p in raw_data['ports'].split(';') if p.strip()]
        else:
            raw_data['ports_list'] = []
        if 'services' in raw_data and isinstance(raw_data['services'], str):
            raw_data['services_list'] = [s.strip() for s in raw_data['services'].split(';') if s.strip()]
        else:
            raw_data['services_list'] = []
        # Копируем cpu_model из snapshot в raw_data для удобства шаблона
        if latest_snapshot.cpu_model:
            raw_data['cpu_model'] = latest_snapshot.cpu_model
        # Количество дисков из disk_info
        if latest_snapshot.disk_info:
            raw_data['disk_count'] = len(latest_snapshot.disk_info)
        else:
            raw_data['disk_count'] = 0
        # Температура из snapshot
        if latest_snapshot.cpu_temperature:
            raw_data['temp_c'] = latest_snapshot.cpu_temperature
    else:
        raw_data['ports_list'] = []
        raw_data['services_list'] = []
        raw_data['disk_count'] = 0
    
    # Статистика
    total_events = host.events.count()
    critical_events = host.events.filter(severity='critical').count()
    warning_events = host.events.filter(severity='warning').count()
    
    # События по типам
    events_by_type = {}
    for et in SecurityEvent.EventType.values:
        label = dict(SecurityEvent.EventType.choices).get(et, et)
        count = host.events.filter(event_type=et).count()
        if count > 0:
            events_by_type[label] = count

    # Последний вход — ищем совпадение с корпоративным пользователем
    latest_login = host.recent_logins.order_by('-login_time').first()
    last_login_user = None
    last_login_fullname = None
    if latest_login:
        # Если вход уже сопоставлен с сотрудником — используем его
        if latest_login.matched_user:
            last_login_user = latest_login.matched_user
            last_login_fullname = f"{last_login_user.last_name} {last_login_user.first_name[0]}.{last_login_user.patronymic[0] if last_login_user.patronymic else ''}.{last_login_user.first_name[0]}."
        else:
            # Ищем пользователя по username, domain_account, first_name, last_name
            last_login_user = AccountUser.objects.filter(
                Q(username__iexact=latest_login.username) |
                Q(domain_account__iexact=latest_login.username) |
                Q(first_name__iexact=latest_login.username) |
                Q(last_name__iexact=latest_login.username)
            ).first()
            if last_login_user:
                last_login_fullname = f"{last_login_user.last_name} {last_login_user.first_name[0]}.{last_login_user.patronymic[0] if last_login_user.patronymic else ''}.{last_login_user.first_name[0]}."

    # Текущие пользователи (из agent inventory)
    current_users = []
    users_raw = raw_data.get('users_list', [])
    if users_raw:
        for u in users_raw:
            if isinstance(u, dict):
                uname = u.get('user', '')
            else:
                uname = str(u)
            if uname:
                # Ищем пользователя в системе
                matched_user = AccountUser.objects.filter(
                    Q(username__iexact=uname) |
                    Q(domain_account__iexact=uname) |
                    Q(first_name__iexact=uname) |
                    Q(last_name__iexact=uname)
                ).first()
                fname = None
                if matched_user:
                    fname = f"{matched_user.last_name} {matched_user.first_name[0]}.{matched_user.patronymic[0] if matched_user.patronymic else ''}.{matched_user.first_name[0]}."
                current_users.append({
                    'username': uname,
                    'user': matched_user,
                    'fullname': fname,
                })

    # История браузеров
    browser_history = []
    browser_events = host.events.filter(event_type='browser_history').order_by('-occurred_at')[:1]
    for ev in browser_events:
        urls = ev.details.get('urls', [])
        if urls:
            browser_history = sorted(urls, key=lambda x: x.get('visited', ''), reverse=True)[:200]
            with open('/tmp/siem-browser-debug.log', 'a') as f:
                f.write(f'{timezone.now()} host={host.hostname}, urls_count={len(urls)}\n')

    # Журнал блокировок экрана
    screen_lock_logs = host.screen_lock_logs.order_by('-timestamp')[:100]

    context = {
        'host': host,
        'recent_events': recent_events,
        'snapshots': snapshots,
        'latest_snapshot': latest_snapshot,
        'inventory_details': inventory_details,
        'raw_data': raw_data,
        'recent_logins': host.recent_logins.select_related('matched_user').order_by('-login_time')[:100],
        'latest_login': latest_login,
        'last_login_user': last_login_user,
        'last_login_fullname': last_login_fullname,
        'current_users': current_users,
        'browser_history': browser_history,
        'screen_lock_logs': screen_lock_logs,
        'total_events': total_events,
        'critical_events': critical_events,
        'warning_events': warning_events,
        'events_by_type': events_by_type,
    }
    return render(request, 'siem/host_detail.html', context)


# ============================================================================
# API-эндпоинты (остаются без изменений)
# ============================================================================

class IngestViewSet(viewsets.ViewSet):
    """Приём событий от агентов."""

    def create(self, request):
        events = request.data
        if isinstance(events, dict):
            events = [events]

        serializer = SecurityEventSerializer(data=events, many=True)
        if not serializer.is_valid():
            import sys
            # Логируем в файл для отладки
            import os
            log_path = '/tmp/siem-ingest-errors.log'
            with open(log_path, 'a') as f:
                f.write(f'{timezone.now()} ERROR: {serializer.errors}\n')
                f.write(f'  Data: {events[:1] if isinstance(events, list) else events}\n\n')
            print(f'❌ INGEST VALIDATION ERROR: {serializer.errors}', file=sys.stderr)
            print(f'   Raw data: {events[:1] if isinstance(events, list) else events}', file=sys.stderr)
            logger.warning(f'Ingest validation error: {serializer.errors}')
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        for item in serializer.validated_data:
            host, _ = Host.objects.get_or_create(
                hostname=item.pop('hostname'),
                defaults={'is_active': True},
            )
            host.last_seen = timezone.now()
            host.save(update_fields=['last_seen'])

            event_type = item.get('event_type')
            details = item.get('details', {})

            # Обработка login/logins_2d/logins_month — парсим историю входов
            if event_type in ('login', 'logins_2d', 'logins_month'):
                self._process_logins(details, host, item.get('occurred_at'))

            # Обработка screen_lock_log — журнал блокировок экрана
            if event_type == 'screen_lock_log':
                self._process_screen_locks(details, host, item.get('occurred_at'))

            # Проверка absence alert для обычных login
            if event_type == 'login':
                self._check_absence_alert(details, host, item.get('occurred_at'))

            SecurityEvent.objects.create(host=host, **item)
            created += 1

        return Response(
            {'accepted': created, 'total': len(events)},
            status=status.HTTP_201_CREATED,
        )

    def _process_logins(self, details, host, occurred_at):
        """Извлекает login-данные из details и сохраняет в RecentLogin.
        
        Ищет пользователя из Accounts по логину. Если не найден — создаёт событие LOGIN_UNKNOWN.
        """
        logins = details.get('logins', [])
        if not logins:
            # Если logins в details нет, пробуем details напрямую
            if 'user' in details and 'at' in details:
                logins = [details]

        for login in logins:
            username = login.get('user', '')
            login_time_str = login.get('at', '')
            source = login.get('source', '')

            if not username or not login_time_str:
                continue

            try:
                login_time = timezone.datetime.fromisoformat(
                    login_time_str.replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                continue

            # Определяем тип входа и IP из source
            login_type = 'console'
            source_ip = None
            
            if source:
                # Проверяем, является ли source IP-адресом
                ip_match = re.match(r'^(\d+\.\d+\.\d+\.\d+)$', source)
                if ip_match:
                    source_ip = ip_match.group(1)
                    login_type = 'console'
                else:
                    if 'ssh' in source.lower() or 'pts' in source.lower():
                        login_type = 'ssh'
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', source)
                        if ip_match:
                            source_ip = ip_match.group(1)
                    elif 'rdp' in source.lower() or 'remote' in source.lower():
                        login_type = 'rdp'
                    else:
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', source)
                        if ip_match:
                            source_ip = ip_match.group(1)

            # Ищем пользователя в Accounts по логину
            matched_user = None
            try:
                matched_user = AccountUser.objects.filter(
                    Q(username__iexact=username) |
                    Q(domain_account__iexact=username) |
                    Q(first_name__iexact=username) |
                    Q(last_name__iexact=username)
                ).first()
            except Exception:
                pass

            # Сохраняем вход (уникально по host + username + login_time)
            _, created = RecentLogin.objects.get_or_create(
                host=host,
                username=username,
                login_time=login_time,
                defaults={
                    'source': source,
                    'matched_user': matched_user,
                    'is_matched': bool(matched_user),
                    'is_screen_locked': details.get('is_locked', False),
                },
            )

            # Если пользователь не найден в Accounts — генерируем событие только при создании
            if not matched_user and created:
                SecurityEvent.objects.create(
                    host=host,
                    event_type='login_unknown',
                    severity='info',
                    message=f'Вход неизвестного пользователя: {username}',
                    details={
                        'username': username,
                        'hostname': host.hostname,
                        'source': source,
                        'login_time': login_time_str,
                    },
                    occurred_at=login_time,
                )

    def _process_screen_locks(self, details, host, occurred_at):
        """Извлекает переходы состояния блокировки экрана и сохраняет в ScreenLockLog."""
        locks = details.get('locks', [])
        if not locks:
            return

        for lock in locks:
            is_locked = lock.get('is_locked', False)
            username = lock.get('username', '')
            session_id = lock.get('session_id', '')
            timestamp_str = lock.get('timestamp', '')

            if not timestamp_str:
                continue

            try:
                timestamp = timezone.datetime.fromisoformat(
                    timestamp_str.replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                continue

            # Определяем state
            state = 'locked' if is_locked else 'unlocked'

            # Создаём запись перехода (уникально по host + date + state)
            ScreenLockLog.objects.get_or_create(
                host=host,
                date=timestamp.date(),
                state=state,
                defaults={
                    'timestamp': timestamp,
                    'username': username,
                    'session_id': session_id,
                },
            )

    def _check_absence_alert(self, details, host, occurred_at):
        """Проверяет, не вошёл ли сотрудник в период отсутствия."""
        username = details.get('user', '')
        if not username or not occurred_at:
            return

        # Ищем активные отпуска сотрудника
        try:
            from accounts.models import User
            employee = User.objects.filter(
                Q(username=username) |
                Q(domain_account__iexact=username) |
                Q(first_name__iexact=username) |
                Q(last_name__iexact=username)
            ).first()

            if not employee:
                return

            active_leaves = EmployeeLeave.objects.filter(
                employee=employee,
                start_date__lte=occurred_at.date(),
                end_date__gte=occurred_at.date(),
                is_approved=True,
            )

            for leave in active_leaves:
                AbsenceAlert.objects.get_or_create(
                    employee=employee,
                    leave=leave,
                    host=host,
                    login_time=occurred_at,
                    defaults={
                        'username': username,
                        'domain_account': employee.domain_account or '',
                        'is_acknowledged': False,
                        'notes': f'Вход в период {leave.get_leave_type_display()}',
                    },
                )
        except Exception:
            # Не блокируем основной поток событий
            pass


class InventoryIngestViewSet(viewsets.ViewSet):
    """Приём снимков инвентаризации."""

    def create(self, request):
        snapshots = request.data
        if isinstance(snapshots, dict):
            snapshots = [snapshots]

        serializer = InventorySnapshotSerializer(data=snapshots, many=True)
        serializer.is_valid(raise_exception=True)

        created = 0
        for item in serializer.validated_data:
            hostname = item.pop('hostname')
            host, _ = Host.objects.get_or_create(
                hostname=hostname,
                defaults={'is_active': True},
            )
            host.last_seen = timezone.now()
            
            # Извлекаем raw данные для обновления Host
            raw = item.get('raw', {})
            if raw:
                update_fields = ['last_seen']
                
                # Обновляем поля Host из raw
                if 'serial' in raw:
                    host.serial_number = raw['serial']
                    update_fields.append('serial_number')
                if 'model' in raw:
                    host.os_info = raw['model']
                    update_fields.append('os_info')
                if 'os' in raw:
                    host.os_info = raw['os']
                    update_fields.append('os_info')
                if 'os_name' in raw and raw['os_name']:
                    host.os_name = raw['os_name']
                    update_fields.append('os_name')
                if 'ip' in raw:
                    # Берём первый IP адрес
                    ips = raw['ip'].split()
                    if ips:
                        host.ip_address = ips[0]
                        update_fields.append('ip_address')
                if 'mac' in raw:
                    # Формат: "eth0:00:1a:2b:3c:4d:e5" или "eth0:aa:bb:cc:dd:ee:ff;wlan0:11:22:33:44:55:66"
                    mac = raw['mac']
                    # Извлекаем первый MAC-адрес (6 групп по 2 hex символа через двоеточие)
                    import re
                    mac_match = re.search(r'([0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5})', mac)
                    if mac_match:
                        # MAC-адрес всегда 17 символов (xx:xx:xx:xx:xx:xx)
                        mac_val = mac_match.group(1)[:17]
                    else:
                        # Fallback: обрезаем до 17 символов
                        mac_val = re.sub(r'[^0-9a-fA-F:]', '', mac)[:17]
                    
                    # Гарантированно обрезаем до 17
                    if len(mac_val) > 17:
                        mac_val = mac_val[:17]
                    
                    if mac_val:
                        host.mac_address = mac_val
                        update_fields.append('mac_address')
                if 'antivirus' in raw:
                    host.antivirus_installed = True
                    host.antivirus_name = raw['antivirus']
                    update_fields.append('antivirus_installed')
                    update_fields.append('antivirus_name')
                # Версия антивируса
                if 'av_version' in raw and raw['av_version']:
                    host.antivirus_version = raw['av_version']
                    update_fields.append('antivirus_version')
                # Дата обновления антивируса
                if 'av_update' in raw and raw['av_update'] and raw['av_update'] != 'не определена':
                    try:
                        host.antivirus_last_update = timezone.datetime.strptime(raw['av_update'], '%Y-%m-%d %H:%M')
                        update_fields.append('antivirus_last_update')
                    except (ValueError, TypeError):
                        pass
                if 'lock_info' in raw:
                    # Извлекаем timeout из строки "timeout: 600"
                    try:
                        timeout = int(raw['lock_info'].split(':')[1].strip())
                        host.screen_lock_timeout = timeout
                        update_fields.append('screen_lock_timeout')
                    except (ValueError, IndexError):
                        pass
                # lock_timeout может быть напрямую
                if 'lock_timeout' in raw and raw['lock_timeout']:
                    try:
                        host.screen_lock_timeout = int(raw['lock_timeout'])
                        update_fields.append('screen_lock_timeout')
                    except (ValueError, TypeError):
                        pass
                # users_list — список текущих пользователей
                if 'users_list' in raw and raw['users_list']:
                    raw['users_list'] = raw['users_list']
                # load_avg и uptime
                if 'load_avg' in raw:
                    raw['load_avg'] = raw['load_avg']
                if 'uptime_hours' in raw and raw['uptime_hours']:
                    try:
                        raw['uptime_hours'] = float(raw['uptime_hours'])
                    except (ValueError, TypeError):
                        raw['uptime_hours'] = None
                if 'uptime_display' in raw:
                    raw['uptime_display'] = raw['uptime_display']
                # Fallback: если uptime_display нет, но есть uptime_hours
                elif raw.get('uptime_hours'):
                    hours = raw['uptime_hours']
                    days = int(hours) // 24
                    rest = int(hours) % 24
                    mins = int((hours % 1) * 60)
                    display = ""
                    if days > 0:
                        display = f"{days} дн. "
                    display += f"{rest} ч. {mins} мин."
                    raw['uptime_display'] = display
                if 'suid_count' in raw and raw['suid_count']:
                    try:
                        raw['suid_count'] = int(raw['suid_count'])
                    except (ValueError, TypeError):
                        raw['suid_count'] = 0
                
                # Обновляем agent_version
                if 'agent_version' in raw:
                    host.agent_version = raw['agent_version']
                    update_fields.append('agent_version')
                
                # Обновляем open_ports из raw
                if 'ports' in raw:
                    ports = raw['ports'].split(';')
                    item['open_ports'] = [p.strip() for p in ports if p.strip()]
                
                # Сохраняем services в raw (не сохраняем в Host)
                # services будут в raw JSON поля InventorySnapshot
                
                if update_fields:
                    host.save(update_fields=update_fields)

            InventorySnapshot.objects.create(host=host, **item)
            created += 1

        return Response(
            {'accepted': created, 'total': len(snapshots)},
            status=status.HTTP_201_CREATED,
        )


class HostListView(generics.ListAPIView):
    """API: список хостов."""
    queryset = Host.objects.all()
    serializer_class = HostSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]


class SecurityEventListView(generics.ListAPIView):
    """API: список событий."""
    serializer_class = SecurityEventSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = SecurityEvent.objects.select_related('host').all()
        host = self.request.query_params.get('host', None)
        if host:
            qs = qs.filter(host__hostname__icontains=host)
        event_type = self.request.query_params.get('type', None)
        if event_type:
            qs = qs.filter(event_type=event_type)
        severity = self.request.query_params.get('severity', None)
        if severity:
            qs = qs.filter(severity=severity)
        days = self.request.query_params.get('days', 7)
        try:
            days = int(days)
        except (ValueError, TypeError):
            days = 7
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = qs.filter(occurred_at__gte=cutoff)
        return qs


class SIEMDashboardView(generics.GenericAPIView):
    """API: сводная статистика."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        day_ago = now - timezone.timedelta(days=1)
        week_ago = now - timezone.timedelta(weeks=1)

        total_hosts = Host.objects.count()
        active_hosts = Host.objects.filter(is_active=True).count()
        cutoff = timezone.now() - timezone.timedelta(hours=24)
        offline_hosts = Host.objects.filter(last_seen__lt=cutoff).count()

        events_today = SecurityEvent.objects.filter(occurred_at__gte=day_ago).count()
        events_critical_today = SecurityEvent.objects.filter(
            occurred_at__gte=day_ago, severity='critical'
        ).count()
        events_this_week = SecurityEvent.objects.filter(
            occurred_at__gte=week_ago
        ).count()

        type_counts = {}
        for et in SecurityEvent.EventType.values:
            label = dict(SecurityEvent.EventType.choices).get(et, et)
            count = SecurityEvent.objects.filter(
                occurred_at__gte=day_ago, event_type=et
            ).count()
            type_counts[label] = count

        recent_critical = list(
            SecurityEvent.objects.filter(severity='critical')
            .select_related('host')
            .order_by('-occurred_at')[:10]
        )
        recent_critical_data = []
        for ev in recent_critical:
            recent_critical_data.append({
                'id': ev.id,
                'host': ev.host.hostname,
                'type': ev.get_event_type_display(),
                'message': ev.message,
                'occurred_at': ev.occurred_at,
            })

        offline_host_list = list(
            Host.objects.filter(last_seen__lt=cutoff)
            .order_by('hostname')[:10]
        )
        offline_host_data = [
            {
                'hostname': h.hostname,
                'last_seen': h.last_seen,
                'total_events': h.total_events,
            }
            for h in offline_host_list
        ]

        return Response({
            'hosts': {
                'total': total_hosts,
                'active': active_hosts,
                'offline': offline_hosts,
            },
            'events': {
                'today': events_today,
                'critical_today': events_critical_today,
                'this_week': events_this_week,
                'by_type': type_counts,
            },
            'recent_critical': recent_critical_data,
            'offline_hosts': offline_host_data,
        })


# ============================================================================
# API: приём истории входов от агента
# ============================================================================

class LoginHistoryIngestViewSet(viewsets.ViewSet):
    """Приём истории входов от агентов."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def create(self, request):
        logins = request.data
        if isinstance(logins, dict):
            logins = [logins]

        accepted = 0
        for item in logins:
            hostname = item.get('hostname')
            if not hostname:
                continue

            host, _ = Host.objects.get_or_create(
                hostname=hostname,
                defaults={'is_active': True},
            )
            host.last_seen = timezone.now()
            host.save(update_fields=['last_seen'])

            LoginHistory.objects.create(
                host=host,
                username=item.get('username', ''),
                domain_account=item.get('domain_account', ''),
                login_time=item.get('login_time', timezone.now()),
                logout_time=item.get('logout_time'),
                login_type=item.get('login_type', ''),
                source_ip=item.get('source_ip'),
                session_id=item.get('session_id', ''),
            )
            accepted += 1

        return Response(
            {'accepted': accepted, 'total': len(logins)},
            status=status.HTTP_201_CREATED,
        )


# ============================================================================
# API: приём расширенной информации о хосте
# ============================================================================

class ExtendedHostInfoViewSet(viewsets.ViewSet):
    """Приём расширенной информации о хосте (OS, антивирус, MAC и т.д.)."""
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def create(self, request):
        serializer = ExtendedHostInfoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        hostname = data.get('hostname')
        if not hostname:
            return Response(
                {'error': 'hostname required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        host, _ = Host.objects.get_or_create(
            hostname=hostname,
            defaults={'is_active': True},
        )

        update_fields = []
        for field in [
            'os_type', 'os_install_date', 'mac_address',
            'antivirus_installed', 'antivirus_name', 'antivirus_version',
            'antivirus_last_update', 'screen_lock_timeout',
        ]:
            if field in data and data[field] is not None:
                setattr(host, field, data[field])
                update_fields.append(field)

        host.last_seen = timezone.now()
        update_fields.append('last_seen')
        host.save(update_fields=update_fields)

        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


# ============================================================================
# HTML: управление отсутствиями сотрудников
# ============================================================================

def leaves_list(request):
    """Список всех периодов отсутствия."""
    search = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    leaves = EmployeeLeave.objects.select_related('employee', 'approved_by').all()

    if search:
        leaves = leaves.filter(
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search) |
            Q(employee__username__icontains=search)
        )

    if status_filter == 'active':
        today = timezone.now().date()
        leaves = leaves.filter(start_date__lte=today, end_date__gte=today, is_approved=True)
    elif status_filter == 'pending':
        leaves = leaves.filter(is_approved=False)

    leaves = leaves.order_by('-start_date')

    context = {
        'leaves': leaves,
        'search': search,
        'status': status_filter,
    }
    return render(request, 'siem/leaves_list.html', context)


def leave_detail(request, pk):
    """Детали периода отсутствия."""
    leave = get_object_or_404(
        EmployeeLeave.objects.select_related('employee', 'approved_by'), pk=pk
    )
    context = {'leave': leave}
    return render(request, 'siem/leave_detail.html', context)


def leave_create(request):
    """Создание нового периода отсутствия."""
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        leave_type = request.POST.get('leave_type')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        reason = request.POST.get('reason', '')

        try:
            employee = User.objects.get(id=employee_id)
            leave = EmployeeLeave.objects.create(
                employee=employee,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                is_approved=False,
            )
            return redirect('siem:leave_detail', pk=leave.pk)
        except User.DoesNotExist:
            return render(request, 'siem/leave_create.html', {'error': 'Сотрудник не найден'})

    employees = User.objects.filter(is_active=True).order_by('last_name', 'first_name')
    return render(request, 'siem/leave_create.html', {'employees': employees})


def leave_edit(request, pk):
    """Редактирование периода отсутствия."""
    leave = get_object_or_404(EmployeeLeave, pk=pk)

    if request.method == 'POST':
        leave.leave_type = request.POST.get('leave_type')
        leave.start_date = request.POST.get('start_date')
        leave.end_date = request.POST.get('end_date')
        leave.reason = request.POST.get('reason', '')
        leave.is_approved = request.POST.get('is_approved') == 'on'
        leave.save()
        return redirect('siem:leave_detail', pk=leave.pk)

    return render(request, 'siem/leave_edit.html', {'leave': leave})


def leave_delete(request, pk):
    """Удаление периода отсутствия."""
    leave = get_object_or_404(EmployeeLeave, pk=pk)
    if request.method == 'POST':
        leave.delete()
        return redirect('siem:leaves_list')
    return render(request, 'siem/leave_delete.html', {'leave': leave})


# ============================================================================
# HTML: алерты входа в период отсутствия
# ============================================================================

def alerts_list(request):
    """Список алертов входа в период отсутствия."""
    search = request.GET.get('search', '')
    acknowledged = request.GET.get('ack', '')

    alerts = AbsenceAlert.objects.select_related(
        'employee', 'leave', 'host', 'acknowledged_by'
    ).all()

    if search:
        alerts = alerts.filter(
            Q(employee__username__icontains=search) |
            Q(employee__first_name__icontains=search) |
            Q(employee__last_name__icontains=search)
        )

    if acknowledged == 'yes':
        alerts = alerts.filter(is_acknowledged=True)
    elif acknowledged == 'no':
        alerts = alerts.filter(is_acknowledged=False)

    alerts = alerts.order_by('-created_at')

    context = {
        'alerts': alerts,
        'search': search,
        'acknowledged': acknowledged,
    }
    return render(request, 'siem/alerts_list.html', context)


def alert_acknowledge(request, pk):
    """Подтверждение алерта."""
    alert = get_object_or_404(AbsenceAlert, pk=pk)
    if request.method == 'POST':
        alert.is_acknowledged = True
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.notes = request.POST.get('notes', '')
        alert.save()
        return redirect('siem:alerts_list')
    return render(request, 'siem/alert_ack.html', {'alert': alert})


# ============================================================================
# HTML: история входов
# ============================================================================

def login_history_list(request):
    """Список всех входов с фильтрацией."""
    search = request.GET.get('search', '')
    host_filter = request.GET.get('host', '')
    matched_filter = request.GET.get('matched', '')
    days = request.GET.get('days', 14)

    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 14

    logins = RecentLogin.objects.select_related('host', 'matched_user').all()

    if search:
        logins = logins.filter(
            Q(username__icontains=search) |
            Q(host__hostname__icontains=search)
        )

    if host_filter:
        logins = logins.filter(host__hostname__icontains=host_filter)

    if matched_filter == 'yes':
        logins = logins.filter(is_matched=True)
    elif matched_filter == 'no':
        logins = logins.filter(is_matched=False)

    cutoff = timezone.now() - timezone.timedelta(days=days)
    logins = logins.filter(login_time__gte=cutoff)

    logins = logins.order_by('-login_time')

    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(logins, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'logins': page_obj,
        'search': search,
        'host_filter': host_filter,
        'matched': matched_filter,
        'days': days,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }
    return render(request, 'siem/login_history.html', context)


def login_history_detail(request, pk):
    """Детали конкретного входа."""
    login = get_object_or_404(
        RecentLogin.objects.select_related('host', 'matched_user'), pk=pk
    )
    # События этого же пользователя на этом хосте
    related_logins = RecentLogin.objects.filter(
        host=login.host,
        username=login.username,
    ).order_by('-login_time')[:20]

    context = {
        'login': login,
        'related_logins': related_logins,
    }
    return render(request, 'siem/login_history_detail.html', context)


# ============================================================================
# HTML: журнал блокировок экрана
# ============================================================================

def screen_lock_log_list(request):
    """Список переходов состояния блокировки экрана."""
    search = request.GET.get('search', '')
    host_filter = request.GET.get('host', '')
    locked_filter = request.GET.get('locked', '')
    days = request.GET.get('days', 14)

    try:
        days = int(days)
    except (ValueError, TypeError):
        days = 14

    logs_qs = ScreenLockLog.objects.select_related('host').all()

    if search:
        logs_qs = logs_qs.filter(
            Q(username__icontains=search) |
            Q(host__hostname__icontains=search)
        )

    if host_filter:
        logs_qs = logs_qs.filter(host__hostname__icontains=host_filter)

    if locked_filter == 'locked':
        logs_qs = logs_qs.filter(state='locked')
    elif locked_filter == 'unlocked':
        logs_qs = logs_qs.filter(state='unlocked')

    cutoff = timezone.now() - timezone.timedelta(days=days)
    logs_qs = logs_qs.filter(timestamp__gte=cutoff)

    logs_qs = logs_qs.order_by('-timestamp')

    # Считаем статистику по всем записям за период (без пагинации)
    all_logs_qs = ScreenLockLog.objects.select_related('host').filter(timestamp__gte=cutoff)
    if search:
        all_logs_qs = all_logs_qs.filter(
            Q(username__icontains=search) |
            Q(host__hostname__icontains=search)
        )
    if host_filter:
        all_logs_qs = all_logs_qs.filter(host__hostname__icontains=host_filter)

    total_count = all_logs_qs.count()
    locked_count = all_logs_qs.filter(state='locked').count()
    unlocked_count = all_logs_qs.filter(state='unlocked').count()
    unique_hosts = all_logs_qs.values('host').distinct().count()

    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(logs_qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'logs': page_obj,
        'search': search,
        'host_filter': host_filter,
        'locked': locked_filter,
        'days': days,
        'total_count': total_count,
        'locked_count': locked_count,
        'unlocked_count': unlocked_count,
        'unique_hosts': unique_hosts,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }
    return render(request, 'siem/screen_lock_log.html', context)


# ============================================================================
# Справка
# ============================================================================

def help_page(request):
    """Страница справки по событиям SIEM."""
    return render(request, 'siem/help.html')
