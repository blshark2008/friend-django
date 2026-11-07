/**
 * Скрипты для приложения messaging
 */

document.addEventListener('DOMContentLoaded', function () {

    // ===== Фильтр: сброс =====
    const filterForm = document.querySelector('form[method="get"]');
    if (filterForm) {
        const resetBtn = filterForm.querySelector('[type="reset"]');
        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                setTimeout(() => {
                    filterForm.submit();
                }, 100);
            });
        }
    }

    // ===== Выбор получателей: подсветка =====
    const recipientSelect = document.querySelector('#id_recipients');
    if (recipientSelect) {
        recipientSelect.addEventListener('change', function () {
            const count = this.selectedOptions.length;
            const hint = this.nextElementSibling?.nextElementSibling;
            if (hint && hint.classList.contains('form-text')) {
                hint.textContent = `Выбрано: ${count} ${getDeclension(count, ['получатель', 'получателя', 'получателей'])}`;
            }
        });
    }

    // ===== Авто-сохранение черновика =====
    const contentTextarea = document.querySelector('#id_content');
    const draftBtn = document.querySelector('[data-draft]');
    if (contentTextarea && draftBtn) {
        let saveTimeout;
        contentTextarea.addEventListener('input', function () {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                draftBtn.classList.add('sending-indicator');
                // Здесь можно добавить AJAX-сохранение черновика
                setTimeout(() => {
                    draftBtn.classList.remove('sending-indicator');
                }, 500);
            }, 2000);
        });
    }

    // ===== Подтверждение удаления =====
    const deleteForms = document.querySelectorAll('form[data-confirm-delete]');
    deleteForms.forEach(function (form) {
        form.addEventListener('submit', function (e) {
            if (!confirm('Вы уверены, что хотите удалить это сообщение? Это действие нельзя отменить.')) {
                e.preventDefault();
            }
        });
    });

    // ===== Копирование текста =====
    const copyButtons = document.querySelectorAll('[data-copy]');
    copyButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            const targetId = this.getAttribute('data-copy');
            const target = document.getElementById(targetId);
            if (target) {
                navigator.clipboard.writeText(target.textContent).then(() => {
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="bi bi-check"></i> Скопировано';
                    this.classList.add('btn-success');
                    this.classList.remove('btn-outline-secondary');
                    setTimeout(() => {
                        this.innerHTML = originalText;
                        this.classList.remove('btn-success');
                        this.classList.add('btn-outline-secondary');
                    }, 2000);
                });
            }
        });
    });
});

/**
 * Склонение существительных
 */
function getDeclension(number, titles) {
    const forms = titles;
    const abs = Math.abs(number) % 100;
    const lastDigit = abs % 10;

    if (abs > 10 && abs < 20) return forms[2];
    if (lastDigit > 1 && lastDigit < 5) return forms[1];
    if (lastDigit === 1) return forms[0];
    return forms[2];
}
