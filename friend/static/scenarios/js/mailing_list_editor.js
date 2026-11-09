/*
 * Редактор JSON списка рассылки (mailing_list_json)
 * Данные загружаются из шаблонной переменной — никаких fetch
 * В JSON сохраняется id, в таблице показывается наименование
 */

window.MailingListEditor = (function () {
    'use strict';

    var currentItems = [];
    var textareaId;
    var containerId;
    var data = { users: [], departments: [], groups: [] };
    // Lookup таблицы: id -> name
    var userNames = {};
    var deptNames = {};
    var groupNames = {};
    var roleNames = {};

    // ========================================================================
    // Инициализация
    // ========================================================================

    function init(textareaEl) {
        textareaId = textareaEl.id;
        containerId = textareaId + '_ml_editor';

        // Данные уже встроены в шаблон — копируем, не ссылаемся
        if (window._mailingListData) {
            data = JSON.parse(JSON.stringify(window._mailingListData));
            // Строим lookup
            if (data.users) {
                data.users.forEach(function (u) {
                    userNames[u.id] = u.tab_number + ' — ' + u.last_name + ' ' + u.first_name;
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
            if (data.roles) {
                data.roles.forEach(function (r) {
                    roleNames[r.id] = r.name;
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

        // Три кнопки
        html += '<div class="d-flex gap-2 mb-3 flex-wrap">';
        html += '<button type="button" class="btn btn-outline-primary" onclick="MailingListEditor.openModal(\'user\',\'' + containerId + '\')">';
        html += '<i class="bi bi-person me-1"></i>Сотрудник</button>';
        html += '<button type="button" class="btn btn-outline-primary" onclick="MailingListEditor.openModal(\'department\',\'' + containerId + '\')">';
        html += '<i class="bi bi-building me-1"></i>Подразделение</button>';
        html += '<button type="button" class="btn btn-outline-primary" onclick="MailingListEditor.openModal(\'mail_group\',\'' + containerId + '\')">';
        html += '<i class="bi bi-people me-1"></i>Группа</button>';
        html += '<button type="button" class="btn btn-outline-primary" onclick="MailingListEditor.openModal(\'role\',\'' + containerId + '\')">';
        html += '<i class="bi bi-person-badge me-1"></i>Роль</button>';
        html += '</div>';

        // Список добавленных
        html += '<div class="mb-3">';
        html += '<label class="form-label fw-bold">Список рассылки (' + currentItems.length + ' элементов)</label>';

        if (currentItems.length === 0) {
            html += '<div class="text-muted text-center py-4 border rounded bg-light">';
            html += '<i class="bi bi-inbox" style="font-size:2.5rem;opacity:0.3;"></i>';
            html += '<p class="mt-2 mb-0">Список пуст — добавьте сотрудников, подразделения или группы</p>';
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
            '<button type="button" class="btn btn-sm btn-outline-danger p-0" style="width:28px;height:28px;line-height:1;" ' +
            'onclick="MailingListEditor.removeItem(\'' + cid + '\', ' + index + ')" title="Удалить">' +
            '<i class="bi bi-trash"></i></button>' +
            '</td></tr>';
    }

    function getTypeInfo(type) {
        var infos = {
            'user': { label: 'Сотрудник', icon: 'bi-person' },
            'department': { label: 'Подразделение', icon: 'bi-building' },
            'mail_group': { label: 'Группа рассылки', icon: 'bi-people' },
            'role': { label: 'Роль', icon: 'bi-person-badge' }
        };
        return infos[type] || { label: type, icon: 'bi-circle' };
    }

    // Получаем имя по id из lookup-таблицы
    function getName(type, id) {
        switch (type) {
            case 'user': return userNames[id] || id;
            case 'department': return deptNames[id] || id;
            case 'mail_group': return groupNames[id] || id;
            default: return id;
        }
    }

    // ========================================================================
    // Модальные окна
    // ========================================================================

    function openModal(type, cid) {
        containerId = cid;
        var modalId = cid + '_search_modal';
        var existing = document.getElementById(modalId);
        if (existing) existing.remove();

        var typeInfo = {
            'user': { title: 'Добавить сотрудника', icon: 'bi-person' },
            'department': { title: 'Добавить подразделение', icon: 'bi-building' },
            'mail_group': { title: 'Добавить группу рассылки', icon: 'bi-people' },
            'role': { title: 'Добавить по роли', icon: 'bi-person-badge' }
        }[type] || { title: 'Добавить', icon: 'bi-plus' };

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
        var placeholder = 'Поиск...';
        if (type === 'user') placeholder = 'Фамилия, табельный номер...';
        bodyHtml += '<input type="text" class="form-control form-control-lg" ';
        bodyHtml += 'id="' + modalId + '_search" placeholder="' + placeholder + '" autocomplete="off">';
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
            case 'department': items = data.departments || []; break;
            case 'mail_group': items = data.groups || []; break;
            case 'role': items = data.roles || []; break;
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
            var id = getId(item, type);
            var name = getName(type, id);
            var added = isItemAdded(type, id);

            var btnClass = 'list-group-item list-group-item-action';
            if (added) btnClass += ' disabled opacity-50';

            html += '<button type="button" class="' + btnClass + '" ';
            html += 'onclick="MailingListEditor.addItemFromModal(\'' + type + '\',' + id + ',\'' + containerId + '\',\'' + modalId + '\')" ';
            if (added) html += 'title="Уже добавлен"';
            html += '>';
            html += '<div class="d-flex w-100 justify-content-between align-items-center">';
            html += '<span>' + esc(name) + '</span>';
            if (added) html += '<span class="badge bg-secondary">Добавлен</span>';
            html += '</div>';

            if (type === 'mail_group' && item.member_count !== undefined) {
                html += '<small class="text-muted">' + item.member_count + ' участников</small>';
            }

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
            case 'department':
                return (item.name || '').toLowerCase().indexOf(query) >= 0;
            case 'mail_group':
                return (item.name || '').toLowerCase().indexOf(query) >= 0;
            case 'role':
                return (item.name || '').toLowerCase().indexOf(query) >= 0;
            default:
                return false;
        }
    }

    function getId(item, type) {
        switch (type) {
            case 'user': return item.id;
            case 'department': return item.id;
            case 'mail_group': return item.id;
            case 'role': return item.id;
            default: return null;
        }
    }

    function getName(type, id) {
        switch (type) {
            case 'user': return userNames[id] || id;
            case 'department': return deptNames[id] || id;
            case 'mail_group': return groupNames[id] || id;
            case 'role': return roleNames[id] || id;
            default: return id;
        }
    }

    function isItemAdded(type, id) {
        for (var i = 0; i < currentItems.length; i++) {
            if (currentItems[i].type === type && currentItems[i].value === id) return true;
        }
        return false;
    }

    // ========================================================================
    // Добавление/удаление
    // ========================================================================

    function addItemFromModal(type, id, cid, modalId) {
        if (isItemAdded(type, id)) return;

        currentItems.push({ type: type, value: id });
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
    var textarea = document.querySelector('textarea[name="mailing_list_json"]');
    if (textarea) {
        MailingListEditor.init(textarea);
    }
});
