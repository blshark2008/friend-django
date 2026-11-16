#!/usr/bin/env python3
"""
Удаляет все персональные данные из XML-файлов HL7 CDA.
- patientRole: оставляет только providerOrganization
- assignedPerson: удаляет целиком (ФИО врачей/авторов)
"""

import os
import xml.etree.ElementTree as ET

DIR = "/home/user/Загрузки/Лаба 01"
NS_HL7 = "urn:hl7-org:v3"


def clean_file(xml_file: str) -> bool:
    try:
        tree = ET.parse(xml_file)
    except ET.ParseError as e:
        print(f"  ОШИБКА парсинга: {e}")
        return False

    root = tree.getroot()

    # 1. patientRole — оставляем только providerOrganization
    for patient_role in root.iter(f"{{{NS_HL7}}}patientRole"):
        to_remove = []
        for child in list(patient_role):
            tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag_name != "providerOrganization":
                to_remove.append(child)
        for elem in to_remove:
            patient_role.remove(elem)

    # 2. assignedPerson — удаляем целиком
    for parent in root.iter():
        for child in list(parent):
            if child.tag == f"{{{NS_HL7}}}assignedPerson":
                parent.remove(child)

    tree.write(xml_file, encoding="UTF-8", xml_declaration=True)
    return True


def main():
    ok = 0
    skipped = 0
    for fname in sorted(os.listdir(DIR)):
        if not fname.endswith(".xml"):
            continue
        fpath = os.path.join(DIR, fname)
        print(f"Обработка: {fname}")
        if clean_file(fpath):
            ok += 1
        else:
            skipped += 1

    print(f"\nОбработано: {ok}, Пропущено: {skipped}")


if __name__ == "__main__":
    main()
