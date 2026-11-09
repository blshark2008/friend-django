/*
 * Редактор JSON для message_json
 * Типы: buttons, number, text_pattern, buttons_with_number
 */

window.MessageJsonEditor = (function () {
    'use strict';

    // Поля для каждого типа
    var FIELD_SCHEMAS = {
        buttons: {
            table: true,
            columns: ['Текст кнопки'],
            fieldKeys: ['text'],
            fields: [
                { key: 'text', label: 'Текст кнопки', type: 'text', required: true },
            ]
        },
        number: {
            table: false,
            fields: [
                { key: 'result_code', label: 'Код результата', type: 'text', required: true, placeholder: 'COUNT, AMOUNT, etc.' },
                { key: 'validation.min', label: 'Минимум', type: 'number', default: '' },
                { key: 'validation.max', label: 'Максимум', type: 'number', default: '' },
            ]
        },
        text_pattern: {
            table: false,
            fields: [
                { key: 'result_code', label: 'Код результата', type: 'text', required: true, placeholder: 'DATA, INFO, etc.' },
                { key: 'pattern', label: 'Регулярное выражение', type: 'text', required: true, placeholder: '^(\\w+)\\s*(\\d+)$' },
                { key: 'fields', label: 'Имена полей (через запятую)', type: 'text', required: true, placeholder: 'name, count' },
            ]
        },
        'buttons_with_number': {
            table: true,
            columns: ['Текст кнопки'],
            fieldKeys: ['text', 'ask_number'],
            fields: [
                { key: 'text', label: 'Текст кнопки', type: 'text', required: true },
                { key: 'ask_number', label: 'Запрос числа', type: 'select', choices: ['Нет', 'Да'] },
            ]
        }
    };

    var currentData = {};
    var currentType = '';
    var rows = [];
    var textareaId;
    var containerId;

    function init(textareaEl) {
        textareaId = textareaEl.id;
        var container = document.createElement('div');
        container.id = containerId = textareaId + '_editor';
        container.className = 'message-json-editor';

        // Загружаем существующие данные ДО очистки
        var existing = textareaEl.value;
        if (existing) {
            try {
                currentData = JSON.parse(existing);
            } catch (e) {
                currentData = {};
            }
        }

        // Вставляем после textarea, скрываем textarea
        textareaEl.parentNode.insertBefore(container, textareaEl.nextSibling);
        textareaEl.style.display = 'none';
        textareaEl.value = '';

        currentType = currentData.type || '';
        rows = buildRows();

        render(container);
    }

    function buildRows() {
        if (!currentType) return [];

        var schema = FIELD_SCHEMAS[currentType];
        if (!schema || !schema.table) return [];

        if (currentType === 'buttons' || currentType === 'buttons_with_number') {
            var options = currentData.options || [];
            return options.map(function (opt) {
                return {
                    text: opt.text || '',
                    result_code: opt.result_code || '',
                    ask_number: opt.ask_number ? true : false
                };
            });
        }

        return [];
    }

    function render(container) {
        var html = '';

        // Выбор типа
        html += '<div class="json-editor-toolbar mb-3">';
        html += '<label class="form-label fw-bold">Тип сбора ответа</label>';
        html += '<select class="form-select d-inline-block w-auto" id="' + containerId + '_type">';
        html += '<option value="">— Выберите тип —</option>';
        html += '<option value="buttons" ' + (currentType === 'buttons' ? 'selected' : '') + '>Кнопки</option>';
        html += '<option value="number" ' + (currentType === 'number' ? 'selected' : '') + '>Число с валидацией</option>';
        html += '<option value="text_pattern" ' + (currentType === 'text_pattern' ? 'selected' : '') + '>Текст по шаблону</option>';
        html += '<option value="buttons_with_number" ' + (currentType === 'buttons_with_number' ? 'selected' : '') + '>Кнопки + запрос числа</option>';
        html += '</select>';

        if (currentType) {
            var schema = FIELD_SCHEMAS[currentType];
            if (!schema.table) {
                // Поля для не-табличных типов
                html += '<button class="btn btn-primary btn-sm mt-2" onclick="MessageJsonEditor.editFields(\'' + containerId + '\')">' +
                    '<i class="bi bi-pencil me-1"></i>Настроить</button>';
            } else {
                html += '<div class="mt-2"><span class="badge bg-info">' + rows.length + ' строк</span></div>';
            }
        }

        html += '</div>';

        // Таблица для кнопок
        if (currentType && FIELD_SCHEMAS[currentType].table) {
            html += '<div class="table-responsive">';
            html += '<table class="table table-sm table-hover mb-0" id="' + containerId + '_table">';
            html += '<thead class="table-light"><tr>';
            FIELD_SCHEMAS[currentType].columns.forEach(function (col) {
                html += '<th>' + col + '</th>';
            });
            if (currentType === 'buttons_with_number') {
                html += '<th>Запрос числа</th>';
            }
            html += '</tr></thead>';
            html += '<tbody>';
            rows.forEach(function (row, i) {
                html += '<tr>';
                html += '<td>' + esc(row.text) + ' <button type="button" class="btn btn-sm btn-outline-primary me-1" onclick="MessageJsonEditor.editRow(\'' + containerId + '\', ' + i + ')" title="Редактировать"><i class="bi bi-pencil"></i></button> <button type="button" class="btn btn-sm btn-outline-danger" onclick="MessageJsonEditor.deleteRow(\'' + containerId + '\', ' + i + ')" title="Удалить"><i class="bi bi-trash"></i></button></td>';
                if (currentType === 'buttons_with_number') {
                    html += '<td>' + (row.ask_number ? '<span class="badge bg-success">Да</span>' : '<span class="badge bg-secondary">Нет</span>') + '</td>';
                }
                html += '</tr>';
            });
            html += '</tbody></table>';
            html += '</div>';

            html += '<button type="button" class="btn btn-outline-primary btn-sm mt-2" onclick="MessageJsonEditor.addRow(\'' + containerId + '\')">';
            html += '<i class="bi bi-plus-circle me-1"></i>Добавить строку</button>';
        }

        // Предпросмотр JSON
        html += '<div class="mt-3">';
        html += '<label class="form-label fw-bold">Предпросмотр JSON</label>';
        html += '<pre class="bg-light border rounded p-2 mb-0" style="max-height:200px;overflow:auto;font-size:0.85rem;" id="' + containerId + '_preview">Пусто — выберите тип и заполните данные</pre>';
        html += '</div>';

        container.innerHTML = html;

        // Обработчик изменения типа
        document.getElementById(containerId + '_type').addEventListener('change', function () {
            var newType = this.value;
            if (newType !== currentType) {
                currentType = newType;
                rows = buildRows();
                render(container);
                autoSave();
            }
        });

        updatePreview(container.id);
    }

    function editFields(containerId) {
        var schema = FIELD_SCHEMAS[currentType];
        var win = window.open('', '_blank', 'width=500,height=400');
        var html = '<!DOCTYPE html><html><head><title>Настройка JSON</title>';
        html += '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">';
        html += '</head><body class="p-4"><h5>Настройка: ' + currentType + '</h5>';
        html += '<form id="fieldsForm">';

        schema.fields.forEach(function (f) {
            html += '<div class="mb-3">';
            html += '<label class="form-label">' + f.label + '</label>';
            html += '<input type="text" class="form-control" name="' + f.key + '" ';
            if (f.type === 'number') html += 'type="number" ';
            html += 'placeholder="' + (f.placeholder || '') + '" ';
            if (f.required) html += 'required ';
            var val = getNestedValue(currentData, f.key);
            if (val !== undefined && val !== null) html += 'value="' + esc(String(val)) + '"';
            html += '>';
            html += '</div>';
        });

        html += '<button type="submit" class="btn btn-primary">Сохранить</button>';
        html += '<button type="button" class="btn btn-secondary" onclick="window.close()">Отмена</button>';
        html += '</form></body></html>';

        win.document.write(html);
        win.document.close();

        win.document.getElementById('fieldsForm').addEventListener('submit', function (e) {
            e.preventDefault();
            var fd = new FormData(this);
            var newResultCode = fd.get('result_code');
            var newMin = fd.get('validation.min');
            var newMax = fd.get('validation.max');
            var newPattern = fd.get('pattern');
            var newFields = fd.get('fields');

            currentData = { type: currentType };
            currentData.result_code = newResultCode || '';

            if (currentType === 'number') {
                currentData.validation = {};
                if (newMin !== '') currentData.validation.min = Number(newMin);
                if (newMax !== '') currentData.validation.max = Number(newMax);
            } else if (currentType === 'text_pattern') {
                currentData.pattern = newPattern || '';
                currentData.fields = newFields ? newFields.split(',').map(function (f) { return f.trim(); }).filter(Boolean) : [];
            }

            autoSave();
            win.close();
        });
    }

    function addRow(containerId) {
        showModal('Добавить строку', containerId, -1);
    }

    function editRow(containerId, index) {
        showModal('Редактировать строку', containerId, index);
    }

    function deleteRow(containerId, index) {
        rows.splice(index, 1);
        render(document.getElementById(containerId));
        autoSave();
    }

    function showModal(title, containerId, index) {
        var schema = FIELD_SCHEMAS[currentType];
        var row = index >= 0 ? rows[index] : {};

        // Модальное окно (Bootstrap)
        var modalId = containerId + '_modal_' + Date.now();
        var existing = document.getElementById(modalId);
        if (existing) existing.remove();

        var formId = 'rowForm_' + Date.now();

        var modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = modalId;
        modal.tabIndex = -1;
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-labelledby', modalId + '_label');

        var modalDialog = document.createElement('div');
        modalDialog.className = 'modal-dialog';
        modalDialog.setAttribute('role', 'document');

        var modalContent = document.createElement('div');
        modalContent.className = 'modal-content';

        // Header
        var modalHeader = document.createElement('div');
        modalHeader.className = 'modal-header';
        var modalTitle = document.createElement('h5');
        modalTitle.className = 'modal-title';
        modalTitle.id = modalId + '_label';
        modalTitle.textContent = title;
        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'btn-close';
        closeBtn.setAttribute('data-bs-dismiss', 'modal');
        closeBtn.setAttribute('aria-label', 'Закрыть');
        modalHeader.appendChild(modalTitle);
        modalHeader.appendChild(closeBtn);

        // Body
        var modalBody = document.createElement('div');
        modalBody.className = 'modal-body';
        var form = document.createElement('form');
        form.id = formId;

        schema.fields.forEach(function (f) {
            var fieldDiv = document.createElement('div');
            fieldDiv.className = 'mb-3';

            var label = document.createElement('label');
            label.className = 'form-label';
            label.textContent = f.label;
            label.setAttribute('for', formId + '_' + f.key);

            var input;
            if (f.type === 'select') {
                input = document.createElement('select');
                input.className = 'form-select';
                input.name = f.key;
                input.id = formId + '_' + f.key;
                f.choices.forEach(function (ch) {
                    var val = ch.toLowerCase() === 'да';
                    var option = document.createElement('option');
                    option.value = val;
                    option.textContent = ch;
                    if (row[f.key] === val) option.selected = true;
                    input.appendChild(option);
                });
            } else {
                input = document.createElement('input');
                input.type = 'text';
                input.className = 'form-control';
                input.name = f.key;
                input.id = formId + '_' + f.key;
                input.placeholder = f.placeholder || '';
                if (f.required) input.required = true;
                input.value = row[f.key] || '';
            }

            fieldDiv.appendChild(label);
            fieldDiv.appendChild(input);
            form.appendChild(fieldDiv);
        });

        modalBody.appendChild(form);

        // Footer
        var modalFooter = document.createElement('div');
        modalFooter.className = 'modal-footer';
        var saveBtn = document.createElement('button');
        saveBtn.type = 'button';
        saveBtn.className = 'btn btn-primary';
        saveBtn.textContent = 'Сохранить';
        var cancelBtn = document.createElement('button');
        cancelBtn.type = 'button';
        cancelBtn.className = 'btn btn-secondary';
        cancelBtn.setAttribute('data-bs-dismiss', 'modal');
        cancelBtn.textContent = 'Отмена';
        modalFooter.appendChild(saveBtn);
        modalFooter.appendChild(cancelBtn);

        // Assemble
        modalContent.appendChild(modalHeader);
        modalContent.appendChild(modalBody);
        modalContent.appendChild(modalFooter);
        modalDialog.appendChild(modalContent);
        modal.appendChild(modalDialog);
        document.body.appendChild(modal);

        // Show
        var bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        // Save
        modal._formData = { containerId: containerId, index: index };

        // Обработчик кнопки "Сохранить"
        saveBtn.addEventListener('click', function () {
            // Валидация
            var textInput = form.querySelector('input[name="text"]');
            if (textInput && !textInput.value.trim()) {
                textInput.classList.add('is-invalid');
                textInput.focus();
                return;
            }
            if (textInput) textInput.classList.remove('is-invalid');

            var fd = new FormData(form);
            var newRow = {};
            schema.fields.forEach(function (f) {
                var val = fd.get(f.key);
                if (f.type === 'select') {
                    newRow[f.key] = val === 'true' || val === true;
                } else {
                    newRow[f.key] = val || '';
                }
            });

            // Автогенерация result_code для кнопок
            if ((currentType === 'buttons' || currentType === 'buttons_with_number') && index < 0) {
                newRow.result_code = generateUniqueCode();
            }

            // Если редактируем — тоже перегенерируем если пусто
            if ((currentType === 'buttons' || currentType === 'buttons_with_number') && index >= 0 && !newRow.result_code) {
                newRow.result_code = generateUniqueCode();
            }

            if (index >= 0) {
                rows[index] = newRow;
            } else {
                rows.push(newRow);
            }

            bsModal.hide();
            render(document.getElementById(containerId));
            autoSave();
        });
    }

    function generateUniqueCode() {
        // Генерируем случайную 8-символьную последовательность
        var chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        var code = '';
        for (var i = 0; i < 8; i++) {
            code += chars.charAt(Math.floor(Math.random() * chars.length));
        }

        // Проверяем уникальность
        var baseCode = code;
        var counter = 1;
        while (rows.some(function (r) { return r.result_code === code; })) {
            code = baseCode + counter;
            counter++;
        }

        return code;
    }

    function updatePreview(containerId) {
        var preview = document.getElementById(containerId + '_preview');
        if (!preview) return;

        var json = buildJSON();
        preview.textContent = JSON.stringify(json, null, 2);
    }

    function buildJSON() {
        if (!currentType) return {};

        var schema = FIELD_SCHEMAS[currentType];
        var result = { type: currentType };

        if (currentType === 'buttons' || currentType === 'buttons_with_number') {
            result.options = rows.map(function (row) {
                var opt = { text: row.text, result_code: row.result_code || '' };
                if (row.ask_number) {
                    opt.ask_number = { result_code: 'NUMBER' };
                }
                return opt;
            });
        }

        return result;
    }

    function autoSave() {
        var textarea = document.getElementById(textareaId);
        var json = buildJSON();
        textarea.value = JSON.stringify(json);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        updatePreview(document.getElementById(containerId));
    }

    function esc(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function getNestedValue(obj, key) {
        var parts = key.split('.');
        var current = obj;
        for (var i = 0; i < parts.length; i++) {
            if (current === null || current === undefined) return undefined;
            current = current[parts[i]];
        }
        return current;
    }

    // Public API
    return {
        init: init,
        editFields: editFields,
        addRow: addRow,
        editRow: editRow,
        deleteRow: deleteRow
    };
})();

// Автоматическая инициализация при загрузке DOM
document.addEventListener('DOMContentLoaded', function () {
    var textarea = document.querySelector('textarea[name="message_json"]');
    if (textarea) {
        MessageJsonEditor.init(textarea);
    }
});
