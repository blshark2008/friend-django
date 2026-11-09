/*
 * Редактор JSON исключений (exclusion_list_json)
 * Поддерживаемые типы: user, role
 * Данные загружаются из шаблонной переменной
 */

window.ExclusionListEditor = (function () {
    'use strict';

    var currentItems = [];
    var textareaId;
    var containerId;
    var data = { users: [], roles: [], departments: [], groups: [] };
    var userNames = {};
    var roleNames = {};
    var deptNames = {};
    var groupNames = {};

    // ========================================================================
    // Инициализация
    // ========================================================================

    function init(textareaEl) {
        textareaId = textareaEl.id;
        containerId = textareaId + '_excl_editor';

        // Данные уже встроены в шаблон — копируем, не ссылаемся
        if (window._mailingListData) {
            data = JSON.parse(JSON.stringify(window._mailingListData));
            if (data.users) {
                data.users.forEach(function (u) {
                    userNames[u.id] = u.tab_number + ' — ' + u.last_name + ' ' + u.first_name;
                });
            }
            if (data.roles) {
                data.roles.forEach(function (r) {
                    roleNames[r.id] = r.name;
                });
            }
            if (data.departments) {
                data.departments.forEach(function (d) {
                    deptNames[d.id] = d.name;
                });
            }
            if (data.groups) {
                data.groups.forEach(function (g) {
                    groupNames[g.id] = g.name;
                });
            }
        }

        // Загружаем существующие данные из textarea
        var existing = textareaEl.value;
        if (existing) {
            try {
                var parsed = JSON.parse(existing);
                if (Array.isArray(parsed)) {
                    currentItems = parsed;
                }
            } catch (e) {
                currentItems = [];
            }
        }

        textareaEl.style.display = 'none';
        textareaEl.value = '';

        var container = document.createElement('div');
        container.id = containerId;
        container.className = 'mailing-list-editor';
        textareaEl.parentNode.insertBefore(container, textareaEl.nextSibling);

        render(container);
        
        // Восстанавливаем значение textarea если есть данные
        if (currentItems.length > 0) {
            textareaEl.value = JSON.stringify(currentItems);
        }
    }

    // ========================================================================
    // Рендер
    // ========================================================================

    function render(container) {
        var html = '';

        // Четыре кнопки
        html += '<div class="d-flex gap-2 mb-3 flex-wrap">';
        html += '<button type="button" class="btn btn-outline-danger" onclick="ExclusionListEditor.openModal(\'user\',\'' + containerId + '\')">';
        html += '<i class="bi bi-person-x me-1"></i>Исключить сотрудника</button>';
        html += '<button type="button" class="btn btn-outline-danger" onclick="ExclusionListEditor.openModal(\'role\',\'' + containerId + '\')">';
        html += '<i class="bi bi-person-x me-1"></i>Исключить по роли</button>';
        html += '<button type="button" class="btn btn-outline-danger" onclick="ExclusionListEditor.openModal(\'department\',\'' + containerId + '\')">';
        html += '<i class="bi bi-building-x me-1"></i>Исключить подразделение</button>';
        html += '<button type="button" class="btn btn-outline-danger" onclick="ExclusionListEditor.openModal(\'mail_group\',\'' + containerId + '\')">';
        html += '<i class="bi bi-people-x me-1"></i>Исключить группу</button>';
        html += '</div>';

        // Список исключённых
        html += '<div class="mb-3">';
        html += '<label class="form-label fw-bold">Исключения (' + currentItems.length + ' элементов)</label>';

        if (currentItems.length === 0) {
            html += '<div class="text-muted text-center py-4 border rounded bg-light">';
            html += '<i class="bi bi-check-circle" style="font-size:2.5rem;opacity:0.3;"></i>';
            html += '<p class="mt-2 mb-0">Никого не исключено</p>';
            html += '</div>';
        } else {
            html += '<div class="table-responsive">';
            html += '<table class="table table-sm table-hover mb-0">';
            html += '<thead class="table-light"><tr><th>Тип</th><th>Значение</th><th style="width:50px;"></th></tr></thead>';
            html += '<tbody>';
            for (var i = 0; i < currentItems.length; i++) {
                html += renderRow(currentItems[i], i, containerId);
            }
            html += '</tbody></table></div>';
        }

        html += '</div>';

        // Предпросмотр JSON
        html += '<div class="mt-3">';
        html += '<label class="form-label fw-bold">Предпросмотр JSON</label>';
        html += '<pre class="bg-light border rounded p-2 mb-0" style="max-height:200px;overflow:auto;font-size:0.8rem;" ';
        html += 'id="' + containerId + '_preview">';
        html += JSON.stringify(currentItems, null, 2) || 'Пусто';
        html += '</pre>';
        html += '</div>';

        container.innerHTML = html;
    }

    function renderRow(item, index, cid) {
        var typeInfo = getTypeInfo(item.type);
        var name = getName(item.type, item.value);
        return '<tr>' +
            '<td><i class="bi ' + typeInfo.icon + ' me-1"></i>' + typeInfo.label + '</td>' +
            '<td>' + esc(name) + '</td>' +
            '<td>' +
            '<button type="button" class="btn btn-sm btn-outline-success p-0" style="width:28px;height:28px;line-height:1;" ' +
            'onclick="ExclusionListEditor.removeItem(\'' + cid + '\', ' + index + ')" title="Убрать из исключений">' +
            '<i class="bi bi-check-lg"></i></button>' +
            '</td></tr>';
    }

    function getTypeInfo(type) {
        var infos = {
            'user': { label: 'Сотрудник', icon: 'bi-person-x' },
            'role': { label: 'Роль', icon: 'bi-person-badge-x' },
            'department': { label: 'Подразделение', icon: 'bi-building-x' },
            'mail_group': { label: 'Группа рассылки', icon: 'bi-people-x' }
        };
        return infos[type] || { label: type, icon: 'bi-circle' };
    }

    function getName(type, value) {
        switch (type) {
            case 'user': return userNames[value] || value;
            case 'role': return roleNames[value] || value;
            case 'department': return deptNames[value] || value;
            case 'mail_group': return groupNames[value] || value;
            default: return value;
        }
    }

    // ========================================================================
    // Модальные окна
    // ========================================================================

    function openModal(type, cid) {
        containerId = cid;
        var modalId = cid + '_excl_modal';
        var existing = document.getElementById(modalId);
        if (existing) existing.remove();

        var typeInfo = {
            'user': { title: 'Исключить сотрудника', icon: 'bi-person-x' },
            'role': { title: 'Исключить по роли', icon: 'bi-person-badge-x' },
            'department': { title: 'Исключить подразделение', icon: 'bi-building-x' },
            'mail_group': { title: 'Исключить группу рассылки', icon: 'bi-people-x' }
        }[type] || { title: 'Исключить', icon: 'bi-x-circle' };

        var modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = modalId;
        modal.tabIndex = -1;
        modal.setAttribute('role', 'dialog');

        var dialog = document.createElement('div');
        dialog.className = 'modal-dialog modal-lg';
        dialog.setAttribute('role', 'document');

        var content = document.createElement('div');
        content.className = 'modal-content';

        var header = document.createElement('div');
        header.className = 'modal-header';
        header.innerHTML = '<h5 class="modal-title"><i class="bi ' + typeInfo.icon + ' me-2"></i>' + typeInfo.title + '</h5>';
        var closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'btn-close';
        closeBtn.setAttribute('data-bs-dismiss', 'modal');
        closeBtn.setAttribute('aria-label', 'Закрыть');
        header.appendChild(closeBtn);
        content.appendChild(header);

        var body = document.createElement('div');
        body.className = 'modal-body';
        var bodyHtml = '<div class="mb-3">';
        bodyHtml += '<input type="text" class="form-control form-control-lg" ';
        bodyHtml += 'id="' + modalId + '_search" placeholder="Поиск..." autocomplete="off">';
        bodyHtml += '</div>';
        bodyHtml += '<div id="' + modalId + '_results"></div>';
        body.innerHTML = bodyHtml;
        content.appendChild(body);

        var footer = document.createElement('div');
        footer.className = 'modal-footer';
        footer.innerHTML = '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>';
        content.appendChild(footer);

        dialog.appendChild(content);
        modal.appendChild(dialog);
        document.body.appendChild(modal);

        var bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        var searchInput = document.getElementById(modalId + '_search');
        var resultsDiv = document.getElementById(modalId + '_results');

        // Показываем подсказку, пока не введён поиск
        renderResults(type, modalId, '', resultsDiv);

        // Поиск с debounce через onkeyup
        var debounceTimer;
        searchInput.onkeyup = function () {
            clearTimeout(debounceTimer);
            var self = this;
            debounceTimer = setTimeout(function () {
                renderResults(type, modalId, self.value, resultsDiv);
            }, 150);
        };

        setTimeout(function () { searchInput.focus(); }, 200);

        modal.addEventListener('hidden.bs.modal', function () {
            modal.remove();
        });
    }

    function renderResults(type, modalId, query, resultsDiv) {
        var items = [];
        switch (type) {
            case 'user': items = data.users || []; break;
            case 'role': items = data.roles || []; break;
            case 'department': items = data.departments || []; break;
            case 'mail_group': items = data.groups || []; break;
        }

        // Пустой запрос — показываем подсказку
        if (!query || !query.trim()) {
            resultsDiv.innerHTML = '<div class="text-center text-muted py-5">';
            resultsDiv.innerHTML += '<i class="bi bi-search" style="font-size:3rem;opacity:0.2;"></i>';
            resultsDiv.innerHTML += '<p class="mt-3 mb-0">Начните вводить для поиска</p>';
            resultsDiv.innerHTML += '</div>';
            return;
        }

        // Фильтруем
        var q = query.toLowerCase().trim();
        var filtered = items.filter(function (item) {
            return matchesItem(item, type, q);
        });

        if (filtered.length === 0) {
            resultsDiv.innerHTML = '<div class="text-center text-muted py-4">';
            resultsDiv.innerHTML += '<i class="bi bi-search" style="font-size:2rem;opacity:0.3;"></i>';
            resultsDiv.innerHTML += '<p class="mt-2 mb-0">Ничего не найдено</p>';
            resultsDiv.innerHTML += '</div>';
            return;
        }

        var html = '<div class="list-group list-group-flush" style="max-height:400px;overflow-y:auto;">';
        for (var i = 0; i < filtered.length; i++) {
            var item = filtered[i];
            var value = getValue(item, type);
            var name = getName(type, value);
            var added = isItemAdded(type, value);

            var btnClass = 'list-group-item list-group-item-action';
            if (added) btnClass += ' disabled opacity-50';

            html += '<button type="button" class="' + btnClass + '" ';
            html += 'onclick="ExclusionListEditor.addItemFromModal(\'' + type + '\',' + value + ',\'' + containerId + '\',\'' + modalId + '\')" ';
            if (added) html += 'title="Уже в исключениях"';
            html += '>';
            html += '<div class="d-flex w-100 justify-content-between align-items-center">';
            html += '<span>' + esc(name) + '</span>';
            if (added) html += '<span class="badge bg-danger">В исключениях</span>';
            html += '</div>';
            html += '</button>';
        }
        html += '</div>';

        resultsDiv.innerHTML = html;
    }

    function matchesItem(item, type, query) {
        switch (type) {
            case 'user':
                var tab = (item.tab_number || '').toLowerCase();
                var ln = (item.last_name || '').toLowerCase();
                var fn = (item.first_name || '').toLowerCase();
                var pn = (item.patronymic || '').toLowerCase();
                var dept = (item.department || '').toLowerCase();
                return tab.indexOf(query) >= 0 || ln.indexOf(query) >= 0 || fn.indexOf(query) >= 0 || pn.indexOf(query) >= 0 || dept.indexOf(query) >= 0;
            case 'role':
                return (item.name || '').toLowerCase().indexOf(query) >= 0;
            case 'department':
                return (item.name || '').toLowerCase().indexOf(query) >= 0;
            case 'mail_group':
                return (item.name || '').toLowerCase().indexOf(query) >= 0;
            default:
                return false;
        }
    }

    function getValue(item, type) {
        switch (type) {
            case 'user': return item.id;
            case 'role': return item.id;
            case 'department': return item.id;
            case 'mail_group': return item.id;
            default: return null;
        }
    }

    function isItemAdded(type, value) {
        for (var i = 0; i < currentItems.length; i++) {
            if (currentItems[i].type === type && currentItems[i].value === value) return true;
        }
        return false;
    }

    // ========================================================================
    // Добавление/удаление
    // ========================================================================

    function addItemFromModal(type, value, cid, modalId) {
        if (isItemAdded(type, value)) return;

        currentItems.push({ type: type, value: value });
        render(document.getElementById(cid));
        autoSave();

        // Обновляем модалку
        var searchInput = document.getElementById(modalId + '_search');
        if (searchInput) {
            renderResults(type, modalId, searchInput.value, document.getElementById(modalId + '_results'));
        }
    }

    function removeItem(cid, index) {
        currentItems.splice(index, 1);
        render(document.getElementById(cid));
        autoSave();
    }

    // ========================================================================
    // Сохранение
    // ========================================================================

    function autoSave() {
        var textarea = document.getElementById(textareaId);
        textarea.value = JSON.stringify(currentItems);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        updatePreview();
    }

    function updatePreview() {
        var preview = document.getElementById(containerId + '_preview');
        if (!preview) return;
        preview.textContent = JSON.stringify(currentItems, null, 2);
    }

    // ========================================================================
    // Утилиты
    // ========================================================================

    function esc(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Public API
    return {
        init: init,
        openModal: openModal,
        addItemFromModal: addItemFromModal,
        removeItem: removeItem
    };
})();

// Автоматическая инициализация
document.addEventListener('DOMContentLoaded', function () {
    var textarea = document.querySelector('textarea[name="exclusion_list_json"]');
    if (textarea) {
        ExclusionListEditor.init(textarea);
    }
});
