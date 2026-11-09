from django.contrib import admin
from .models import Message, MessageRecipient, MailGroup


@admin.register(MessageRecipient)
class MessageRecipientAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'message_preview', 'delivery_channel', 'delivery_status', 'sent_at']
    list_filter = ['delivery_status', 'delivery_channel']
    search_fields = ['recipient__last_name', 'recipient__first_name', 'message__title']
    readonly_fields = ['sent_at', 'delivered_at', 'read_at']

    def message_preview(self, obj):
        return obj.message.title or obj.message.content[:50]
    message_preview.short_description = 'Сообщение'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['title_preview', 'sender', 'channel', 'priority', 'status', 'created_at', 'recipient_count']
    list_filter = ['status', 'channel', 'priority', 'created_at']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at', 'sent_at']
    date_hierarchy = 'created_at'
    list_per_page = 20

    def title_preview(self, obj):
        return obj.title or obj.content[:50]
    title_preview.short_description = 'Заголовок/Содержание'

    def recipient_count(self, obj):
        return obj.recipient_count
    recipient_count.short_description = 'Получателей'


@admin.register(MailGroup)
class MailGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'description_preview', 'member_count', 'users_count', 'depts_count', 'created_by', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['name', 'description']
    filter_horizontal = ['users', 'departments']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'
    list_per_page = 20

    def description_preview(self, obj):
        return obj.description[:50] if obj.description else '—'
    description_preview.short_description = 'Описание'

    def users_count(self, obj):
        return obj.users.count()
    users_count.short_description = 'Пользователей'

    def depts_count(self, obj):
        return obj.departments.count()
    depts_count.short_description = 'Подразделений'
