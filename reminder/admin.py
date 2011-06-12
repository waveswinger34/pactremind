#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4


from django.contrib import admin
from models import *

#class ConnectionInline(admin.TabularInline):
#    model = Connection
#    extra = 1

class IncomingMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'received_at', 'text', 'network',) 

class SubjectAdmin(admin.ModelAdmin):
    list_display = ('phone_number','message_id', 'messages_left', 'active',) 



admin.site.register(IncomingMessage, IncomingMessageAdmin)
admin.site.register(Subject,SubjectAdmin)

