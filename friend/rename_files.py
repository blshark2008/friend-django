#!/usr/bin/env python3
"""
Переименовывает XML-файлы в закодированные имена (MD5 хеш).
Создаёт CSV-таблицу соответствия: старое имя -> новое имя.
"""

import os
import hashlib
import csv

DIR = "/home/user/Загрузки/Лаба 01"


def encode_name(original: str) -> str:
    """Генерирует хеш MD5 от имени файла и возвращает .xml с хешем."""
    md5 = hashlib.md5(original.encode("utf-8")).hexdigest()
    return f"{md5}.xml"


def main():
    mapping = []  # (old_name, new_name)

    xml_files = sorted(
        f for f in os.listdir(DIR) if f.endswith(".xml")
    )

    for old_name in xml_files:
        new_name = encode_name(old_name)
        old_path = os.path.join(DIR, old_name)
        new_path = os.path.join(DIR, new_name)

        # Если имя уже совпадает (редко), пропускаем
        if old_name == new_name:
            continue

        os.rename(old_path, new_path)
        mapping.append((old_name, new_name))
        print(f"{old_name} -> {new_name}")

    # Записываем таблицу соответствия
    csv_path = os.path.join(DIR, "mapping_old_new.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Старое наименование", "Новое наименование"])
        for old_name, new_name in mapping:
            writer.writerow([old_name, new_name])

    print(f"\nТаблица сохранена: {csv_path}")
    print(f"Всего переименовано файлов: {len(mapping)}")


if __name__ == "__main__":
    main()
