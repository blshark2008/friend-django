from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


# ============================================================================
# Многоуровневые типы оборудования
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
    """Возвращает подтипы для данной категории."""
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
]


# ============================================================================
# Справочник брендов
# ============================================================================

class Brand(models.Model):
    """Бренд (производитель) оборудования."""

    name = models.CharField('Название', max_length=100, unique=True, db_index=True)
    slug = models.SlugField('Тег', max_length=100, unique=True, blank=True, db_index=True)
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
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
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

    # --- Многоуровневый тип ---
    category = models.CharField(
        'Категория', max_length=20, choices=EQUIPMENT_CATEGORIES,
        default=EQUIPMENT_CATEGORY_COMPUTER, db_index=True,
    )
    subtype = models.CharField(
        'Подтип', max_length=30, choices=EQUIPMENT_SUBTYPES,
        default=COMPUTER_SUBTYPE_DESKTOP, db_index=True,
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

    # --- SIEM ---
    last_scan = models.DateTimeField('Последний скан', blank=True, null=True)

    # --- Даты ---
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Оборудование'
        verbose_name_plural = 'Оборудование'
        ordering = ['category', 'subtype', 'inventory_number']
        indexes = [
            models.Index(fields=['category', 'subtype']),
            models.Index(fields=['assigned_user']),
            models.Index(fields=['responsible_user']),
            models.Index(fields=['archived', 'is_active']),
        ]

    def __str__(self):
        user = f' — {self.assigned_user}' if self.assigned_user else ''
        subtype_display = self.get_subtype_display()
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
        """Возвращает читаемую метку типа (категория/подтип)."""
        return self.get_subtype_display()

    @property
    def category_label(self):
        """Возвращает читаемую метку категории."""
        return self.get_category_display()

    def get_subtypes_for_current_category(self):
        """Возвращает доступные подтипы для текущей категории."""
        return get_subtypes_for_category(self.category)

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
            subtype=self.subtype,
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
    """Настройки отображения полей для подтипов оборудования."""

    subtype = models.CharField(
        'Подтип', max_length=30, choices=EQUIPMENT_SUBTYPES,
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
        unique_together = ['subtype', 'field_name']
        ordering = ['subtype', 'sort_order', 'field_name']

    def __str__(self):
        return f"{self.get_subtype_display()} — {self.field_label or self.field_name}"


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
# Справочник полей для каждого подтипа
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
    
    # Статусы
    ('status', 'Статус', 'Статус'),
    ('is_active', 'Активен', 'Статус'),
    ('archived', 'В архиве', 'Статус'),
    
    # SIEM
    ('last_scan', 'Последний скан', 'SIEM'),
]
