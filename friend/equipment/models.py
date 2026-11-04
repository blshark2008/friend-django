from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ============================================================================
# Иерархические категории оборудования
# ============================================================================

class EquipmentCategory(models.Model):
    """Иерархическая категория оборудования."""

    name = models.CharField('Название', max_length=255, db_index=True)
    slug = models.SlugField('Слаг', max_length=100, unique=True, blank=True, db_index=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='children', verbose_name='Родитель',
    )
    code_1c = models.CharField('Код 1С', max_length=100, blank=True, default='')
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлена', auto_now=True)

    class Meta:
        verbose_name = 'Категория оборудования'
        verbose_name_plural = 'Категории оборудования'
        ordering = ['name']

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

    @property
    def is_top_level(self):
        return self.parent is None

    @property
    def subcategories(self):
        return self.children.filter(is_active=True)

    @property
    def equipment_count(self):
        return Equipment.objects.filter(
            category=self,
            archived=False,
        ).count()

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ============================================================================
# Многоуровневые типы оборудования (deprecated - use EquipmentCategory)
# ============================================================================

# Категории оборудования
EQUIPMENT_CATEGORY_COMPUTER = 'computer'
EQUIPMENT_CATEGORY_PRINTER = 'printer'
EQUIPMENT_CATEGORY_PERIPHERY = 'periphery'
EQUIPMENT_CATEGORY_OTHER = 'other'

EQUIPMENT_CATEGORIES = [
    (EQUIPMENT_CATEGORY_COMPUTER, 'Компьютерное оборудование'),
    (EQUIPMENT_CATEGORY_PRINTER, 'Принтеры'),
    (EQUIPMENT_CATEGORY_PERIPHERY, 'Периферия'),
    (EQUIPMENT_CATEGORY_OTHER, 'Прочее'),
]

# Подтипы компьютерного оборудования
COMPUTER_SUBTYPE_DESKTOP = 'desktop'
COMPUTER_SUBTYPE_MONOBLOCK = 'monoblock'
COMPUTER_SUBTYPE_LAPTOP = 'laptop'
COMPUTER_SUBTYPE_TABLET = 'tablet'
COMPUTER_SUBTYPE_SYSTEM_UNIT = 'system_unit'
COMPUTER_SUBTYPE_MONITOR = 'monitor'
COMPUTER_SUBTYPE_SERVER = 'server'
COMPUTER_SUBTYPE_THIN_CLIENT = 'thin_client'

COMPUTER_SUBTYPES = [
    (COMPUTER_SUBTYPE_DESKTOP, 'Компьютер'),
    (COMPUTER_SUBTYPE_MONOBLOCK, 'Моноблок'),
    (COMPUTER_SUBTYPE_LAPTOP, 'Ноутбук'),
    (COMPUTER_SUBTYPE_TABLET, 'Планшет'),
    (COMPUTER_SUBTYPE_SYSTEM_UNIT, 'Системный блок'),
    (COMPUTER_SUBTYPE_MONITOR, 'Монитор'),
    (COMPUTER_SUBTYPE_SERVER, 'Сервер'),
    (COMPUTER_SUBTYPE_THIN_CLIENT, 'Тонкий клиент'),
]

# Подтипы принтеров
PRINTER_SUBTYPE_LASER_COLOR = 'laser_color'
PRINTER_SUBTYPE_LASER_BW = 'laser_bw'
PRINTER_SUBTYPE_MFP_LASER = 'mfp_laser'
PRINTER_SUBTYPE_MFP_INKJET = 'mfp_inkjet'

PRINTER_SUBTYPES = [
    (PRINTER_SUBTYPE_LASER_COLOR, 'Принтер лазерный цветной'),
    (PRINTER_SUBTYPE_LASER_BW, 'Принтер лазерный чёрно-белый'),
    (PRINTER_SUBTYPE_MFP_LASER, 'МФУ лазерное'),
    (PRINTER_SUBTYPE_MFP_INKJET, 'МФУ струйное'),
]

# Подтипы периферии
PERIPHERY_SUBTYPE_HEADSET = 'headset'
PERIPHERY_SUBTYPE_SPEAKERS = 'speakers'
PERIPHERY_SUBTYPE_INKJET = 'inkjet'

PERIPHERY_SUBTYPES = [
    (PERIPHERY_SUBTYPE_HEADSET, 'Гарнитура'),
    (PERIPHERY_SUBTYPE_SPEAKERS, 'Колонки'),
    (PERIPHERY_SUBTYPE_INKJET, 'Принтер струйный'),
]

# Подтипы прочего
OTHER_SUBTYPE_DISK_ARRAY = 'disk_array'
OTHER_SUBTYPE_VKS = 'vks'

OTHER_SUBTYPES = [
    (OTHER_SUBTYPE_DISK_ARRAY, 'Дисковая стойка'),
    (OTHER_SUBTYPE_VKS, 'ВКС (видеоконференцсвязь)'),
]

# Все подтипы (для выбора)
EQUIPMENT_SUBTYPES = (
    COMPUTER_SUBTYPES + PRINTER_SUBTYPES + PERIPHERY_SUBTYPES + OTHER_SUBTYPES
)


def get_subtypes_for_category(category):
    """Возвращает подтипы для данной категории (deprecated)."""
    mapping = {
        EQUIPMENT_CATEGORY_COMPUTER: COMPUTER_SUBTYPES,
        EQUIPMENT_CATEGORY_PRINTER: PRINTER_SUBTYPES,
        EQUIPMENT_CATEGORY_PERIPHERY: PERIPHERY_SUBTYPES,
        EQUIPMENT_CATEGORY_OTHER: OTHER_SUBTYPES,
    }
    return mapping.get(category, [])


# Статусы принтеров
PRINTER_STATUS_CHOICES = [
    ('online', 'Онлайн'),
    ('offline', 'Оффлайн'),
    ('maintenance', 'Обслуживание'),
]

# Статусы оборудования
EQUIPMENT_STATUS_CHOICES = [
    ('active', 'Активно'),
    ('maintenance', 'На обслуживании'),
    ('decommissioned', 'Списано'),
    ('pending', 'Не подтверждён учёт'),
    ('confirmed', 'Подтверждён учёт'),
]

# Типы событий истории оборудования
HISTORY_EVENT_MOVE = 'move'
HISTORY_EVENT_REPAIR = 'repair'
HISTORY_EVENT_UPGRADE = 'upgrade'
HISTORY_EVENT_DECOMMISSION = 'decommission'

HISTORY_EVENT_CHOICES = [
    (HISTORY_EVENT_MOVE, 'Перемещение'),
    (HISTORY_EVENT_REPAIR, 'Ремонт'),
    (HISTORY_EVENT_UPGRADE, 'Модернизация'),
    (HISTORY_EVENT_DECOMMISSION, 'Списание'),
]

# Типы ремонтов
REPAIR_TYPE_CHOICES = [
    ('planned', 'Плановый'),
    ('emergency', 'Аварийный/внеплановый'),
    ('preventive', 'Профилактический'),
]

# Итоги ремонтов
REPAIR_RESULT_CHOICES = [
    ('completed', 'Выполнен'),
    ('cancelled', 'Отменён'),
    ('ongoing', 'В процессе'),
    ('warranty', 'По гарантии'),
]

# Итоги модернизаций
UPGRADE_RESULT_CHOICES = [
    ('completed', 'Выполнена'),
    ('cancelled', 'Отменена'),
    ('ongoing', 'В процессе'),
]


# ============================================================================
# Справочник брендов
# ============================================================================

class Brand(models.Model):
    """Бренд (производитель) оборудования."""

    name = models.CharField('Название', max_length=100, unique=True, db_index=True)
    slug = models.SlugField('Тег', max_length=100, blank=True, db_index=True)
    description = models.TextField('Описание', blank=True)
    website = models.URLField('Сайт', blank=True, max_length=255)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        elif not self.slug:
            self.slug = ''
        super().save(*args, **kwargs)


# ============================================================================
# Единая модель оборудования
# ============================================================================

class Equipment(models.Model):
    """Единая модель оборудования с многоуровневыми типами."""

    # --- Основная информация ---
    inventory_number = models.CharField(
        'Инвентарный номер', max_length=50, unique=True,
        db_index=True, default='',
    )
    serial_number = models.CharField(
        'Серийный номер', max_length=100, blank=True, default='',
    )
    name = models.CharField('Название', max_length=255, blank=True, default='')
    brand = models.ForeignKey(
        'Brand', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipment_items', verbose_name='Бренд',
    )
    model = models.CharField('Модель', max_length=255, blank=True, default='')

    # --- Многоуровневый тип (через базу данных) ---
    category = models.ForeignKey(
        EquipmentCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipment_items', verbose_name='Категория',
        db_index=True,
    )
    subcategory = models.ForeignKey(
        EquipmentCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipment_subitems', verbose_name='Подкатегория',
        db_index=True,
    )
    # Старые поля для обратной совместимости (deprecated)
    _category_str = models.CharField(
        'Категория (deprecated)', max_length=20, blank=True, default='',
    )
    _subtype_str = models.CharField(
        'Подтип (deprecated)', max_length=30, blank=True, default='',
    )

    # --- Назначения ---
    assigned_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipment_assigned', verbose_name='Закреплён за',
    )
    responsible_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipment_responsible', verbose_name='Материально ответственный',
    )

    # --- Сетевая информация ---
    hostname = models.CharField('Имя в сети', max_length=255, blank=True)
    mac_address = models.CharField('MAC-адрес', max_length=17, blank=True)
    ip_address = models.CharField('IP-адрес', max_length=45, blank=True)

    # --- Аппаратное обеспечение (компьютерное) ---
    cpu = models.CharField('Процессор', max_length=255, blank=True)
    ram_gb = models.PositiveIntegerField('ОЗУ (ГБ)', blank=True, null=True)
    storage_gb = models.PositiveIntegerField('Диск (ГБ)', blank=True, null=True)

    # --- Программное обеспечение (компьютерное) ---
    os = models.CharField('ОС', max_length=255, blank=True)
    os_version = models.CharField('Версия ОС', max_length=100, blank=True)
    antivirus_engine = models.CharField('Антивирус', max_length=255, blank=True)
    antivirus_active = models.BooleanField('Защита активна', default=False)

    # --- Специфичные поля ---
    # Для ноутбуков/планшетов/монопотребителей
    screen_size = models.CharField('Диагональ экрана', max_length=20, blank=True)

    # Для мониторов
    resolution = models.CharField('Разрешение', max_length=50, blank=True)

    # Для принтеров
    printer_status = models.CharField(
        'Статус', max_length=20, choices=PRINTER_STATUS_CHOICES, default='offline',
    )

    # Для ВКС
    camera_count = models.PositiveIntegerField('Количество камер', default=1)

    # Для телефонов
    phone_number = models.CharField('Внешний номер', max_length=20, blank=True)
    extension = models.CharField('Внутренний номер', max_length=10, blank=True)

    # Для мед. оборудования (если понадобится)
    calibration_date = models.DateField('Дата калибровки', blank=True, null=True)
    next_calibration = models.DateField('След. калибровка', blank=True, null=True)
    status = models.CharField(
        'Статус', max_length=20, choices=EQUIPMENT_STATUS_CHOICES, default='active',
    )

    # --- Расположение ---
    location = models.CharField('Кабинет', max_length=255, blank=True)
    place = models.CharField('Место', max_length=255, blank=True)

    # --- Статусы ---
    is_active = models.BooleanField('Активен', default=True)
    archived = models.BooleanField('В архиве', default=False)

    # --- Бухгалтерская информация ---
    acquisition_date = models.DateField('Дата постановки на учёт', blank=True, null=True,
                                        help_text='Дата принятия на бухгалтерский учёт')
    acquisition_cost = models.DecimalField('Стоимость при покупке', max_digits=15, decimal_places=2,
                                           blank=True, null=True, help_text='В рублях')
    initial_number = models.CharField('Первоначальная стоимость', max_length=20, blank=True, default='',
                                      help_text='Для бухгалтерии')
    useful_life_months = models.PositiveIntegerField('Срок полезного использования (мес.)', blank=True, null=True,
                                                     help_text='Для расчёта амортизации')
    depreciation_method = models.CharField('Метод амортизации', max_length=50, blank=True, default='',
                                           choices=[
                                               ('linear', 'Линейный'),
                                               ('decreasing', 'Уменьшаемого остатка'),
                                               ('proportional', 'По сумме чисел срока'),
                                           ])

    # --- Информация о списании ---
    decommission_date = models.DateField('Дата списания', blank=True, null=True)
    decommission_act = models.CharField('Акт списания', max_length=255, blank=True, default='',
                                        help_text='Номер и дата акта списания')
    decommission_notes = models.TextField('Примечания к списанию', blank=True, default='',
                                          help_text='Причина, основание для списания')
    decommissioned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='decommissioned_equipment', verbose_name='Списал',
    )

    # --- SIEM ---
    last_scan = models.DateTimeField('Последний скан', blank=True, null=True)

    # --- Даты ---
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Оборудование'
        verbose_name_plural = 'Оборудование'
        ordering = ['inventory_number']
        indexes = [
            models.Index(fields=['category', 'subcategory']),
            models.Index(fields=['assigned_user']),
            models.Index(fields=['responsible_user']),
            models.Index(fields=['archived', 'is_active']),
        ]

    def __str__(self):
        user = f' — {self.assigned_user}' if self.assigned_user else ''
        subtype_display = self.type_label
        return f"{self.inventory_number} — {self.name or subtype_display}{user}"

    @property
    def is_secured(self):
        """Проверяет, активна ли защита (для компьютерного оборудования)."""
        return self.antivirus_active

    @property
    def location_display(self):
        """Возвращает строку местоположения."""
        parts = [self.location, self.place]
        return ' — '.join(filter(None, parts))

    @property
    def type_label(self):
        """Возвращает читаемую метку типа (категория/подкатегория)."""
        if self.subcategory:
            return self.subcategory.name
        if self.category:
            return self.category.name
        return ''

    @property
    def category_label(self):
        """Возвращает читаемую метку категории."""
        if self.category:
            return self.category.name
        return ''

    @property
    def full_type_path(self):
        """Возвращает полный путь: Категория → Подкатегория."""
        parts = []
        if self.category:
            parts.append(self.category.name)
        if self.subcategory:
            parts.append(self.subcategory.name)
        return ' → '.join(parts) if parts else ''

    def get_subtypes_for_current_category(self):
        """Возвращает подкатегории для текущей категории (deprecated - use category.children)."""
        if self.category:
            return self.category.children.filter(is_active=True)
        return EquipmentCategory.objects.none()

    def save(self, *args, **kwargs):
        # Автоматически обновляем name из бренда и модели, если не задан
        if not self.name and (self.brand or self.model):
            parts = []
            if self.brand:
                parts.append(str(self.brand))
            if self.model:
                parts.append(self.model)
            self.name = ' '.join(parts)
        super().save(*args, **kwargs)

    def get_visible_fields(self, for_edit=False):
        """Возвращает список видимых полей для данного подтипа."""
        visible_fields = []
        settings = EquipmentFieldSetting.objects.filter(
            subcategory=self.subcategory,
            is_visible=True,
        )
        if not for_edit:
            settings = settings.filter(is_editable=True)
        
        # Получаем все определения полей
        field_map = {f[0]: {'label': f[1], 'group': f[2]} for f in EQUIPMENT_FIELD_DEFINITIONS}
        
        for setting in settings:
            field_info = field_map.get(setting.field_name, {})
            visible_fields.append({
                'name': setting.field_name,
                'label': setting.field_label or field_info.get('label', setting.field_name),
                'group': setting.field_group or field_info.get('group', 'Другое'),
                'editable': setting.is_editable and for_edit,
            })
        
        return visible_fields

    def get_field_value(self, field_name):
        """Возвращает значение поля по имени."""
        return getattr(self, field_name, None)


# ============================================================================
# Назначения оборудования (обобщённые)
# ============================================================================

class EquipmentAssignment(models.Model):
    """Закрепление оборудования за пользователем."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='equipment_assignments',
        verbose_name='Пользователь',
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name='assignments',
        verbose_name='Оборудование',
    )
    assigned_at = models.DateTimeField('Назначен', auto_now_add=True)
    returned_at = models.DateTimeField('Возвращён', blank=True, null=True)
    notes = models.TextField('Примечания', blank=True)
    is_active = models.BooleanField('Активно', default=True)

    class Meta:
        verbose_name = 'Назначение оборудования'
        verbose_name_plural = 'Назначения оборудования'
        ordering = ['-assigned_at']

    def __str__(self):
        status = 'Активно' if self.is_active else 'Возвращено'
        return f"{self.user} — {self.equipment} [{status}]"

    @property
    def is_returned(self):
        return not self.is_active or self.returned_at is not None


# ============================================================================
# Настройки отображения полей для подтипов оборудования
# ============================================================================

class EquipmentFieldSetting(models.Model):
    """Настройки отображения полей для подкатегорий оборудования."""

    subcategory = models.ForeignKey(
        EquipmentCategory, on_delete=models.CASCADE, null=True, blank=True,
        related_name='field_settings', verbose_name='Подкатегория',
        db_index=True,
    )
    field_name = models.CharField(
        'Имя поля', max_length=50,
    )
    field_label = models.CharField(
        'Метка поля', max_length=100, blank=True, default='',
    )
    is_visible = models.BooleanField(
        'Видимое', default=True,
    )
    is_editable = models.BooleanField(
        'Редактируемое', default=True,
    )
    field_group = models.CharField(
        'Группа', max_length=50, blank=True, default='',
        help_text='Группа для отображения (Основное, Характеристики и т.д.)',
    )
    sort_order = models.PositiveIntegerField(
        'Порядок', default=0,
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Настройка поля оборудования'
        verbose_name_plural = 'Настройки полей оборудования'
        unique_together = ['subcategory', 'field_name']
        ordering = ['subcategory', 'sort_order', 'field_name']

    def __str__(self):
        return f"{self.subcategory} — {self.field_label or self.field_name}"


class EquipmentMOLAssignment(models.Model):
    """Закрепление оборудования за материально ответственным лицом (МОЛ)."""

    mol = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='equipment_mol_assignments',
        verbose_name='Материально ответственное лицо',
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name='mol_assignments',
        verbose_name='Оборудование',
    )
    assigned_at = models.DateTimeField('Назначен', auto_now_add=True)
    returned_at = models.DateTimeField('Возвращён', blank=True, null=True)
    notes = models.TextField('Примечания', blank=True)
    is_active = models.BooleanField('Активно', default=True)

    class Meta:
        verbose_name = 'Назначение оборудования МОЛ'
        verbose_name_plural = 'Назначения оборудования МОЛ'
        ordering = ['-assigned_at']

    def __str__(self):
        status = 'Активно' if self.is_active else 'Возвращено'
        return f"{self.mol} — {self.equipment} [{status}]"

    @property
    def is_returned(self):
        return not self.is_active or self.returned_at is not None


# ============================================================================
# Справочник расположения (город → корпус → этаж → кабинет)
# ============================================================================

class City(models.Model):
    """Город."""

    name = models.CharField('Название', max_length=255, db_index=True)
    code = models.CharField('Код', max_length=50, blank=True, default='', db_index=True)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def buildings_count(self):
        return self.buildings.filter(is_active=True).count()

    @property
    def floors_count(self):
        return self.buildings.filter(is_active=True).values_list('pk', flat=True).count()

    @property
    def rooms_count(self):
        return self.buildings.filter(is_active=True).values_list('pk', flat=True).count()


class Building(models.Model):
    """Корпус / здание / блок."""

    city = models.ForeignKey(
        City, on_delete=models.CASCADE, related_name='buildings',
        verbose_name='Город', null=True, blank=True,
    )
    name = models.CharField('Название', max_length=255, db_index=True)
    code = models.CharField('Код', max_length=50, blank=True, default='', db_index=True)
    address = models.CharField('Адрес', max_length=500, blank=True, default='')
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Корпус'
        verbose_name_plural = 'Корпуса'
        ordering = ['city', 'name']

    def __str__(self):
        return f"{self.city} — {self.name}"

    @property
    def floors_count(self):
        return self.floors.filter(is_active=True).count()

    @property
    def rooms_count(self):
        return self.rooms.filter(is_active=True).count()


class Floor(models.Model):
    """Этаж."""

    building = models.ForeignKey(
        Building, on_delete=models.CASCADE, related_name='floors',
        verbose_name='Корпус',
    )
    floor_number = models.PositiveIntegerField('Номер этажа', db_index=True)
    rooms_count = models.PositiveIntegerField('Кол-во кабинетов', default=0)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Этаж'
        verbose_name_plural = 'Этажи'
        ordering = ['building', 'floor_number']
        unique_together = ['building', 'floor_number']

    def __str__(self):
        return f"{self.building} — эт. {self.floor_number}"


class Room(models.Model):
    """Кабинет."""

    building = models.ForeignKey(
        Building, on_delete=models.CASCADE, related_name='rooms',
        verbose_name='Корпус',
    )
    floor = models.ForeignKey(
        Floor, on_delete=models.CASCADE, related_name='rooms',
        verbose_name='Этаж',
    )
    room_number = models.CharField('Номер кабинета', max_length=20, db_index=True)
    capacity = models.PositiveIntegerField('Вместимость', default=1)
    is_active = models.BooleanField('Активен', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Кабинет'
        verbose_name_plural = 'Кабинеты'
        ordering = ['building', 'floor', 'room_number']
        unique_together = ['building', 'floor', 'room_number']

    def __str__(self):
        return f"{self.building} — эт. {self.floor.floor_number} — каб. {self.room_number}"

    @property
    def full_address(self):
        """Полный адрес: Город — Корпус — Этаж — Кабинет."""
        return f"{self.building.city} — {self.building} — эт. {self.floor.floor_number} — каб. {self.room_number}"


# ============================================================================
# История оборудования (перемещения, ремонты, модернизации)
# ============================================================================

class EquipmentMovement(models.Model):
    """История перемещений оборудования."""

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name='movements',
        verbose_name='Оборудование',
    )
    from_location = models.CharField('Откуда', max_length=500, blank=True, default='',
                                     help_text='Предыдущее расположение')
    to_location = models.CharField('Куда', max_length=500, blank=True, default='',
                                   help_text='Новое расположение')
    from_room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movements_from', verbose_name='Из кабинета',
    )
    to_room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='movements_to', verbose_name='В кабинет',
    )
    from_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipment_given', verbose_name='Передал',
    )
    to_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipment_received', verbose_name='Получил',
    )
    moved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='equipment_moved', verbose_name='Выполнил',
    )
    move_date = models.DateField('Дата перемещения', blank=True, null=True)
    move_datetime = models.DateTimeField('Дата/время', auto_now_add=True)
    notes = models.TextField('Примечания', blank=True, default='')
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Перемещение оборудования'
        verbose_name_plural = 'Перемещения оборудования'
        ordering = ['-move_datetime']

    def __str__(self):
        return f"{self.equipment} — {self.from_location} → {self.to_location}"


class EquipmentRepair(models.Model):
    """История ремонтов оборудования."""

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name='repairs',
        verbose_name='Оборудование',
    )
    repair_type = models.CharField(
        'Тип', max_length=20, choices=REPAIR_TYPE_CHOICES, default='emergency',
    )
    description = models.TextField('Описание неисправности/работ', blank=True, default='')
    result = models.CharField(
        'Итог', max_length=20, choices=REPAIR_RESULT_CHOICES, default='ongoing',
    )
    service_company = models.CharField('Сервисная компания', max_length=255, blank=True, default='')
    warranty_number = models.CharField('Номер гарантии', max_length=100, blank=True, default='')
    cost = models.DecimalField('Стоимость ремонта', max_digits=12, decimal_places=2,
                               blank=True, null=True, help_text='В рублях')
    start_date = models.DateField('Дата начала', blank=True, null=True)
    end_date = models.DateField('Дата окончания', blank=True, null=True)
    responsible_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='repairs_responsible', verbose_name='Ответственный',
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='repairs_created', verbose_name='Создал',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Ремонт оборудования'
        verbose_name_plural = 'Ремонты оборудования'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.equipment} — {self.get_result_display()}"


class EquipmentUpgrade(models.Model):
    """История модернизации оборудования."""

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name='upgrades',
        verbose_name='Оборудование',
    )
    description = models.TextField('Описание модернизации', blank=True, default='')
    old_specs = models.TextField('Было', blank=True, default='',
                                 help_text='Предыдущие характеристики')
    new_specs = models.TextField('Стало', blank=True, default='',
                                 help_text='Новые характеристики')
    result = models.CharField(
        'Итог', max_length=20, choices=UPGRADE_RESULT_CHOICES, default='ongoing',
    )
    cost = models.DecimalField('Стоимость модернизации', max_digits=12, decimal_places=2,
                               blank=True, null=True, help_text='В рублях')
    performed_date = models.DateField('Дата выполнения', blank=True, null=True)
    performed_by = models.CharField('Выполнено кем', max_length=255, blank=True, default='')
    responsible_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='upgrades_responsible', verbose_name='Ответственный',
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='upgrades_created', verbose_name='Создал',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Модернизация оборудования'
        verbose_name_plural = 'Модернизации оборудования'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.equipment} — {self.get_result_display()}"


class EquipmentDecommissionRecord(models.Model):
    """Запись о списании оборудования."""

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE, related_name='decommission_records',
        verbose_name='Оборудование',
    )
    act_number = models.CharField('Номер акта', max_length=100, blank=True, default='')
    act_date = models.DateField('Дата акта', blank=True, null=True)
    reason = models.TextField('Причина списания', blank=True, default='')
    commission = models.TextField('Состав комиссии', blank=True, default='',
                                  help_text='ФИО членов комиссии')
    notes = models.TextField('Примечания', blank=True, default='')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='decommission_records', verbose_name='Создал',
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Запись о списании'
        verbose_name_plural = 'Записи о списании'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.equipment} — {self.act_number or 'Списание'}"


# ============================================================================
# Справочник полей для каждого подтипа оборудования
# ============================================================================

# Поля, которые можно скрывать/показывать
EQUIPMENT_FIELD_DEFINITIONS = [
    # Основная информация
    ('inventory_number', 'Инвентарный номер', 'Основное'),
    ('serial_number', 'Серийный номер', 'Основное'),
    ('name', 'Название', 'Основное'),
    ('brand', 'Бренд', 'Основное'),
    ('model', 'Модель', 'Основное'),
    
    # Назначения
    ('assigned_user', 'Закреплён за', 'Назначения'),
    ('responsible_user', 'Материально ответственный', 'Назначения'),
    
    # Сетевая информация
    ('hostname', 'Имя в сети', 'Сеть'),
    ('mac_address', 'MAC-адрес', 'Сеть'),
    ('ip_address', 'IP-адрес', 'Сеть'),
    
    # Аппаратное обеспечение
    ('cpu', 'Процессор', 'Характеристики'),
    ('ram_gb', 'ОЗУ (ГБ)', 'Характеристики'),
    ('storage_gb', 'Диск (ГБ)', 'Характеристики'),
    ('screen_size', 'Диагональ экрана', 'Характеристики'),
    
    # Программное обеспечение
    ('os', 'ОС', 'Программное обеспечение'),
    ('os_version', 'Версия ОС', 'Программное обеспечение'),
    ('antivirus_engine', 'Антивирус', 'Программное обеспечение'),
    ('antivirus_active', 'Защита активна', 'Программное обеспечение'),
    
    # Специфичные поля
    ('resolution', 'Разрешение', 'Характеристики'),
    ('printer_status', 'Статус принтера', 'Статус'),
    ('camera_count', 'Количество камер', 'Характеристики'),
    ('phone_number', 'Внешний номер', 'Телефон'),
    ('extension', 'Внутренний номер', 'Телефон'),
    ('calibration_date', 'Дата калибровки', 'Калибровка'),
    ('next_calibration', 'След. калибровка', 'Калибровка'),
    
    # Расположение
    ('location', 'Кабинет', 'Расположение'),
    ('place', 'Место', 'Расположение'),
    
    # Бухгалтерская информация
    ('acquisition_date', 'Дата постановки на учёт', 'Бухгалтерия'),
    ('acquisition_cost', 'Стоимость покупки', 'Бухгалтерия'),
    ('initial_number', 'Первоначальная стоимость', 'Бухгалтерия'),
    ('useful_life_months', 'Срок полезного использования', 'Бухгалтерия'),
    ('depreciation_method', 'Метод амортизации', 'Бухгалтерия'),
    
    # Информация о списании
    ('decommission_date', 'Дата списания', 'Списание'),
    ('decommission_act', 'Акт списания', 'Списание'),
    ('decommission_notes', 'Примечания к списанию', 'Списание'),
    
    # Статусы
    ('status', 'Статус', 'Статус'),
    ('is_active', 'Активен', 'Статус'),
    ('archived', 'В архиве', 'Статус'),
    
    # SIEM
    ('last_scan', 'Последний скан', 'SIEM'),
]
