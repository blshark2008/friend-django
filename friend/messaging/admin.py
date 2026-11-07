from django.contrib import admin
from .models import Message, MessageRecipient


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
