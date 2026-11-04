from rest_framework import serializers
from django.utils import timezone
from .models import SecurityEvent, InventorySnapshot, Host, RecentLogin, AbsenceAlert


class SecurityEventSerializer(serializers.ModelSerializer):
    """Сериализатор для приёма событий от агентов."""

    hostname = serializers.CharField(write_only=True)

    class Meta:
        model = SecurityEvent
        fields = ['hostname', 'event_type', 'severity', 'message',
                  'details', 'occurred_at']

    def validate_event_type(self, value):
        allowed = {
            'auth_failed', 'auth_success', 'sudo_used', 'file_changed',
            'uid0_added', 'suid_added', 'cron_changed', 'new_port',
            'disk_full', 'kernel_error', 'inventory', 'agent_alive',
            'absence_login', 'login', 'logins_month', 'updates_pending',
            'logins_2d', 'browser_history', 'packages_modified',
            'sudo_failed', 'parsec_events', 'account_changed',
            'suspicious_process', 'new_connection', 'firewall_changed',
            'new_device', 'login_unknown', 'screen_lock_log',
        }
        if value not in allowed:
            raise serializers.ValidationError(
                f'Неизвестный тип события: {value}'
            )
        return value

    def validate_severity(self, value):
        allowed = {'info', 'warning', 'error', 'critical'}
        if value not in allowed:
            raise serializers.ValidationError(
                f'Неизвестная серьёзность: {value}'
            )
        return value

    def create(self, validated_data):
        hostname = validated_data.pop('hostname')
        host, _ = Host.objects.get_or_create(
            hostname=hostname,
            defaults={
                'last_seen': validated_data.get('occurred_at'),
                'is_active': True,
            },
        )
        host.last_seen = validated_data.get('occurred_at')
        host.save(update_fields=['last_seen'])
        return SecurityEvent.objects.create(host=host, **validated_data)


class InventorySnapshotSerializer(serializers.ModelSerializer):
    """Сериализатор для приёма снимков инвентаризации."""

    hostname = serializers.CharField(write_only=True)

    class Meta:
        model = InventorySnapshot
        fields = [
            'hostname', 'cpu_model', 'cpu_temperature', 'ram_mb',
            'disk_info', 'packages_count', 'pending_updates',
            'open_ports', 'antivirus_running', 'current_logged_user', 'raw',
        ]

    def create(self, validated_data):
        hostname = validated_data.pop('hostname')
        host, _ = Host.objects.get_or_create(
            hostname=hostname,
            defaults={'is_active': True},
        )
        host.last_seen = validated_data.get('collected_at')
        host.save(update_fields=['last_seen'])
        return InventorySnapshot.objects.create(
            host=host, **validated_data
        )


class HostSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения списка хостов."""

    is_offline = serializers.BooleanField(read_only=True)
    total_events = serializers.IntegerField(read_only=True)
    critical_events_count = serializers.IntegerField(read_only=True)
    last_snapshot = serializers.SerializerMethodField()

    class Meta:
        model = Host
        fields = [
            'id', 'hostname', 'serial_number', 'os_info', 'os_name', 'os_type',
            'os_install_date', 'ip_address', 'mac_address',
            'agent_version', 'last_seen', 'is_active',
            'antivirus_installed', 'antivirus_name', 'antivirus_version',
            'antivirus_last_update', 'screen_lock_timeout',
            'created_at', 'is_offline',
            'total_events', 'critical_events_count',
            'last_snapshot',
        ]

    def get_last_snapshot(self, obj):
        snap = obj.snapshots.first()
        if snap:
            return {
                'collected_at': snap.collected_at,
                'cpu': snap.cpu_model,
                'cpu_temperature': snap.cpu_temperature,
                'ram_mb': snap.ram_mb,
                'pending_updates': len(snap.pending_updates) if snap.pending_updates else 0,
                'open_ports_count': len(snap.open_ports),
            }
        return None


class RecentLoginSerializer(serializers.ModelSerializer):
    """Сериализатор для приёма истории входов."""

    hostname = serializers.CharField(write_only=True)

    class Meta:
        model = RecentLogin
        fields = [
            'hostname', 'username', 'source',
            'login_time',
        ]

    def create(self, validated_data):
        hostname = validated_data.pop('hostname')
        host, _ = Host.objects.get_or_create(
            hostname=hostname,
            defaults={'is_active': True},
        )
        host.last_seen = timezone.now()
        host.save(update_fields=['last_seen'])
        return RecentLogin.objects.create(host=host, **validated_data)


class ExtendedHostInfoSerializer(serializers.Serializer):
    """Сериализатор для приёма расширенной информации о хосте."""

    hostname = serializers.CharField()
    os_type = serializers.CharField(required=False, allow_blank=True)
    os_install_date = serializers.DateField(required=False, allow_null=True)
    mac_address = serializers.CharField(required=False, allow_blank=True)
    antivirus_installed = serializers.BooleanField(required=False)
    antivirus_name = serializers.CharField(required=False, allow_blank=True)
    antivirus_version = serializers.CharField(required=False, allow_blank=True)
    antivirus_last_update = serializers.DateTimeField(required=False, allow_null=True)
    screen_lock_timeout = serializers.IntegerField(required=False, allow_null=True)
