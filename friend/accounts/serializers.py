from rest_framework import serializers
from .models import Department, Position, InternalGroup, GroupMapping, ADSyncSettings, User


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code_1c', 'parent', 'is_active']


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'name', 'code_1c', 'department', 'is_active']


class InternalGroupSerializer(serializers.ModelSerializer):
    """Сериализатор внутренних групп."""
    users_count = serializers.SerializerMethodField()
    ad_mappings_count = serializers.SerializerMethodField()

    class Meta:
        model = InternalGroup
        fields = [
            'id', 'name', 'description', 'code', 'is_active', 'is_system',
            'created_at', 'updated_at', 'users_count', 'ad_mappings_count',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_users_count(self, obj):
        return obj.users.count()

    def get_ad_mappings_count(self, obj):
        return obj.ad_mappings.count()

    def validate_code(self, value):
        if not value.replace('-', '_').isalnum():
            raise serializers.ValidationError('Код может содержать только буквы, цифры и дефисы.')
        return value


class InternalGroupDetailSerializer(InternalGroupSerializer):
    """Детальный сериализатор внутренней группы с маппингами."""
    ad_mappings = serializers.SerializerMethodField()
    users = serializers.SerializerMethodField()

    class Meta(InternalGroupSerializer.Meta):
        fields = InternalGroupSerializer.Meta.fields + ['ad_mappings', 'users']

    def get_ad_mappings(self, obj):
        mappings = obj.ad_mappings.filter(is_active=True)
        return GroupMappingSerializer(mappings, many=True).data

    def get_users(self, obj):
        users = obj.users.filter(is_active=True)
        return UserSimpleSerializer(users, many=True).data


class GroupMappingSerializer(serializers.ModelSerializer):
    """Сериализатор связей AD-групп с внутренними."""
    internal_group_name = serializers.CharField(
        source='internal_group.name', read_only=True
    )
    internal_group_code = serializers.CharField(
        source='internal_group.code', read_only=True
    )

    class Meta:
        model = GroupMapping
        fields = [
            'id', 'ad_group_name', 'ad_group_dn', 'ad_group_description',
            'internal_group', 'internal_group_name', 'internal_group_code',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'ad_group_description']


class GroupMappingCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания маппинга."""
    internal_group_code = serializers.CharField(write_only=True)
    ad_group_dn = serializers.CharField(required=False, allow_blank=True)
    ad_group_description = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = GroupMapping
        fields = [
            'ad_group_name', 'ad_group_dn', 'ad_group_description',
            'internal_group_code', 'is_active',
        ]

    def validate_internal_group_code(self, value):
        try:
            InternalGroup.objects.get(code=value, is_active=True)
        except InternalGroup.DoesNotExist:
            raise serializers.ValidationError('Внутренняя группа не найдена или не активна.')
        return value

    def create(self, validated_data):
        internal_group_code = validated_data.pop('internal_group_code')
        internal_group = InternalGroup.objects.get(code=internal_group_code, is_active=True)
        return GroupMapping.objects.create(
            internal_group=internal_group,
            **validated_data,
        )


class ADSyncSettingsSerializer(serializers.ModelSerializer):
    """Сериализатор настроек AD синхронизации."""
    is_sync_enabled = serializers.BooleanField(read_only=True, source='is_enabled')
    last_sync_formatted = serializers.DateTimeField(
        source='last_sync', format='%Y-%m-%d %H:%M:%S', read_only=True
    )

    class Meta:
        model = ADSyncSettings
        fields = [
            'id', 'ad_server', 'ad_port', 'ad_use_ssl', 'ad_base_dn',
            'ad_bind_dn', 'ad_bind_password', 'ad_user_search_base',
            'ad_group_search_base', 'ad_user_object_class',
            'ad_user_samaccountname_field', 'ad_user_memberof_field',
            'ad_group_object_class', 'ad_group_cn_field',
            'ad_group_samaccountname_field', 'sync_on_login',
            'sync_interval_hours', 'last_sync', 'last_sync_formatted',
            'is_enabled', 'is_sync_enabled', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'last_sync']
        extra_kwargs = {
            'ad_bind_password': {'write_only': True},
        }

    def update(self, instance, validated_data):
        # Скрываем пароль при частичном обновлении
        if 'ad_bind_password' not in validated_data:
            validated_data.pop('ad_bind_password', None)
            validated_data['ad_bind_password'] = instance.ad_bind_password
        return super().update(instance, validated_data)


class UserSimpleSerializer(serializers.ModelSerializer):
    """Минимальный сериализатор пользователя для вложений."""
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'last_name', 'first_name', 'full_name', 'email']

    def get_full_name(self, obj):
        parts = [obj.last_name, obj.first_name]
        if obj.patronymic:
            parts.append(obj.patronymic)
        return ' '.join(parts)


class UserGroupInfoSerializer(serializers.Serializer):
    """Сериализатор информации о группах пользователя."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()
    description = serializers.CharField()
    source = serializers.ChoiceField(choices=['manual', 'ad'])
