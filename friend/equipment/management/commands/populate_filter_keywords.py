"""
Management command to populate FilterKeyword table with existing NAME_FILTER_KEYWORDS.
Run: python manage.py populate_filter_keywords
"""
from django.core.management.base import BaseCommand
from equipment.models import FilterKeyword


# Existing keywords from views.py (copied for migration)
FILTER_KEYWORDS_DATA = {
    'компьютер': [
        'компьютер', 'системн[ыи]й блок', 'моноблок', 'ноутбук',
        'нетбук', 'планшет', 'тонкий клиент', 'смарт-часы', 'смаРТЧАС',
        'тв-приставка', 'all-in-one', 'aio',
    ],
    'монитор': [
        'монитор', 'дисплей', 'display',
    ],
    'принтер': [
        'принтер', 'мфу', 'мфУ', 'копир', 'лазерн', 'струйн',
        'этикеток', 'плоттер',
    ],
    'периферия': [
        'веб-камер', 'камер[аы]', 'гарнитур', 'наушник', 'динамик', 'колонк',
        'диктофон', 'клавиатур', 'сканер', 'шредер', 'дисков[аые]', 'жестк',
        'сумк[ае] под ноутбук', 'сумк[ае] для ноутбук', 'рутокен',
    ],
    'сеть': [
        'маршрутизатор', 'коммутатор', 'свитч', 'роутер', 'wifi', 'wi-fi',
        'точк[аы] доступ', 'контроллер', 'ip-камер', 'sfp', 'медиа-конвертер',
        'hdm[и]-сплиттер', 'концентратор', 'хаб', 'hub', 'ethernet',
    ],
    'связь': [
        'телефон', 'voip', 'gsm', 'модем', 'сотов', 'беспроводн',
        'радиотелефон', 'терминал сбор', 'факс',
    ],
    'видео': [
        'проектор', 'телевизор', 'тв', 'видеокамер', 'вкс', 'videocam',
    ],
    'медицинское': [
        'кардиограф',
    ],
}


class Command(BaseCommand):
    help = 'Populate FilterKeyword table with existing NAME_FILTER_KEYWORDS from views.py'

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        for category, keywords in FILTER_KEYWORDS_DATA.items():
            for keyword in keywords:
                obj, created = FilterKeyword.objects.get_or_create(
                    keyword=keyword,
                    category=category,
                    defaults={'is_active': True},
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created: {keyword} ({category})')
                    )
                else:
                    skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created: {created_count}, Skipped (already exists): {skipped_count}'
        ))
