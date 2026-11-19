"""Сервис синхронизации групп пользователя с Active Directory."""
import logging
from datetime import datetime, timedelta
from typing import List, Tuple

from django.db import transaction
from django.utils import timezone

from .models import ADSyncSettings, GroupMapping, InternalGroup, User

logger = logging.getLogger(__name__)


class ADGroupSyncService:
    """Сервис для синхронизации внутренних групп с AD-группами."""

    @classmethod
    def sync_user_groups(cls, user: User) -> dict:
        """
        Синхронизировать внутренние группы пользователя на основе AD-групп.

        Returns:
            dict с результатами синхронизации:
                - added: список добавленных групп
                - removed: список удалённых групп
                - errors: список ошибок
        """
        result = {'added': [], 'removed': [], 'errors': []}

        if not ADSyncSettings.get_enabled():
            logger.info(f'AD синхронизация выключена для пользователя {user}')
            return result

        try:
            # Получаем AD-группы пользователя
            ad_groups = cls._get_user_ad_groups(user)
            logger.info(f'Пользователь {user}: найдено {len(ad_groups)} AD-групп: {ad_groups}')

            # Получаем маппинги AD -> InternalGroup
            mappings = cls._get_active_mappings()

            # Строим карту: ad_group_name -> InternalGroup
            ad_to_internal = {}
            for mapping in mappings:
                ad_to_internal[mapping.ad_group_name] = mapping.internal_group

            # Определяем целевые внутренние группы
            target_group_ids = set()
            for ad_group in ad_groups:
                if ad_group in ad_to_internal:
                    target_group_ids.add(ad_to_internal[ad_group].pk)
                    logger.debug(f'AD-группа {ad_group} -> InternalGroup {ad_to_internal[ad_group]}')

            # Получаем текущие внутренние группы пользователя
            current_group_ids = set(user.internal_groups.values_list('pk', flat=True))

            # Определяем добавляемые и удаляемые группы
            groups_to_add = target_group_ids - current_group_ids
            groups_to_remove = current_group_ids - target_group_ids

            # Добавляем новые группы
            for group_id in groups_to_add:
                group = InternalGroup.objects.get(pk=group_id)
                user.internal_groups.add(group)
                result['added'].append(group.name)
                logger.info(f'Добавлена внутренняя группа {group.name} пользователю {user}')

            # Удаляем ненужные группы
            for group_id in groups_to_remove:
                group = InternalGroup.objects.get(pk=group_id)
                user.internal_groups.remove(group)
                result['removed'].append(group.name)
                logger.info(f'Удалена внутренняя группа {group.name} у пользователя {user}')

            user.save(update_fields=['last_login'])  # trigger any signals if needed

        except Exception as e:
            error_msg = f'Ошибка синхронизации для пользователя {user}: {e}'
            logger.error(error_msg, exc_info=True)
            result['errors'].append(error_msg)

        return result

    @classmethod
    def _get_user_ad_groups(cls, user: User) -> List[str]:
        """
        Получить список AD-групп пользователя.

        Пытается подключиться к AD и получить группы через LDAP.
        Если LDAP недоступен, возвращает пустой список.
        """
        settings = ADSyncSettings.get_settings()
        if not settings:
            return []

        try:
            return cls._query_ad_groups(settings, user)
        except Exception as e:
            logger.warning(f'Не удалось подключиться к AD для пользователя {user}: {e}')
            return []

    @classmethod
    def _query_ad_groups(cls, settings: ADSyncSettings, user: User) -> List[str]:
        """Выполнить LDAP-запрос для получения групп пользователя."""
        import ldap  # python-ldap

        # Определяем URL LDAP
        if settings.ad_use_ssl:
            ldap_url = f'ldaps://{settings.ad_server}:{settings.ad_port}'
        else:
            ldap_url = f'ldap://{settings.ad_server}:{settings.ad_port}'

        conn = ldap.initialize(ldap_url)
        conn.set_option(ldap.OPT_REFERRALS, 0)
        conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

        try:
            # Привязка
            conn.simple_bind_s(settings.ad_bind_dn, settings.ad_bind_password)

            # Формируем фильтр поиска пользователя
            username_field = settings.ad_user_samaccountname_field
            if user.username:
                username = user.username.lower()
            elif user.domain_account:
                username = user.domain_account.lower()
            elif user.email:
                username = user.email.split('@')[0].lower()
            else:
                username = user.last_name.lower()

            search_base = settings.ad_user_search_base or settings.ad_base_dn
            user_filter = f'(&({username_field}={username})(objectClass={settings.ad_user_object_class}))'

            # Ищем пользователя
            result = conn.search_s(
                search_base,
                ldap.SCOPE_SUBTREE,
                user_filter,
                [settings.ad_user_memberof_field, 'dn'],
            )

            if not result or len(result) < 2:
                logger.warning(f'Пользователь {username} не найден в AD')
                return []

            user_dn = result[0][0]
            memberof = result[0][1].get(settings.ad_user_memberof_field, [])

            # Извлекаем CN из DN групп
            ad_groups = []
            for group_dn in memberof:
                if isinstance(group_dn, bytes):
                    group_dn = group_dn.decode('utf-8', errors='ignore')
                # CN=GroupName,OU=Groups,DC=domain,DC=local
                parts = group_dn.split(',')
                for part in parts:
                    if part.startswith('CN='):
                        cn = part[3:]
                        ad_groups.append(cn)
                        break

            return list(set(ad_groups))  # unique

        finally:
            conn.unbind_s()

    @classmethod
    def _get_active_mappings(cls) -> List[GroupMapping]:
        """Получить все активные маппинги."""
        return GroupMapping.objects.filter(is_active=True).select_related('internal_group')

    @classmethod
    def sync_all_users(cls) -> dict:
        """
        Синхронизировать группы всех активных пользователей.

        Returns:
            dict с общей статистикой синхронизации.
        """
        settings = ADSyncSettings.get_settings()
        if not settings:
            return {'error': 'Настройки AD не настроены'}

        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        users = UserModel.objects.filter(is_active=True, is_fired=False)
        total = users.count()
        success = 0
        errors = 0

        logger.info(f'Начата массовая синхронизация AD для {total} пользователей')

        for user in users:
            try:
                result = cls.sync_user_groups(user)
                if not result['errors']:
                    success += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                logger.error(f'Ошибка синхронизации пользователя {user}: {e}')

        settings.last_sync = timezone.now()
        settings.save(update_fields=['last_sync'])

        logger.info(f'Синхронизация завершена: {success} успешно, {errors} ошибок')
        return {
            'total': total,
            'success': success,
            'errors': errors,
            'last_sync': settings.last_sync,
        }

    @classmethod
    def get_user_effective_groups(cls, user: User) -> List[dict]:
        """
        Получить эффективные группы пользователя (ручные + AD).

        Returns:
            Список словарей с информацией о группах.
        """
        mappings = cls._get_active_mappings()
        ad_to_internal = {m.ad_group_name: m.internal_group for m in mappings}

        # Получаем AD-группы
        ad_groups = set(cls._get_user_ad_groups(user))

        # Определяем группы из AD
        ad_group_ids = set()
        for ad_group in ad_groups:
            if ad_group in ad_to_internal:
                ad_group_ids.add(ad_to_internal[ad_group].pk)

        # Получаем все внутренние группы пользователя
        user_groups = user.internal_groups.all()

        result = []
        for group in user_groups:
            is_from_ad = group.pk in ad_group_ids
            result.append({
                'id': group.pk,
                'name': group.name,
                'code': group.code,
                'description': group.description,
                'source': 'ad' if is_from_ad else 'manual',
            })

        return result
