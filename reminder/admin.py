#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from django.contrib import admin
from models import *


class IncomingMessageAdmin(admin.ModelAdmin):
    list_display = ('received_at', 'sender', 'text', 'network',) 
    list_filter = ('network',)
    list_display_links = ('sender',)
    date_hierarchy = 'received_at'


class SubjectAdmin(admin.ModelAdmin):
    def registration_date(self, obj):
        return obj.received_at
#    registration_date.short_description = 'Registration date'
    registration_date.admin_order_field = 'received_at'
        
    def contact_number(self, obj):
        return obj.phone_number
    contact_number.admin_order_field = 'phone_number'
    
    list_display = ('registration_date', 'contact_number','message_id', 
                    'messages_left', 'active',)
    list_display_links = ('contact_number',) 
    list_editable = ('message_id', 'messages_left',)
    list_filter = ('active',)
    date_hierarchy = 'received_at'


admin.site.register(IncomingMessage, IncomingMessageAdmin)
admin.site.register(Subject, SubjectAdmin)

