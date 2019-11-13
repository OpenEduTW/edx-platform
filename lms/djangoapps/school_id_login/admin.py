# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from school_id_login.models import Xschools,Xsuser


class XschoolsAdmin(admin.ModelAdmin):
    list_display = ('xschool_id', 'xschool_client', 'return_uri')


class XsuserAdmin(admin.ModelAdmin):
    list_display = ('user', 'nid_linked', 'ask_nid_link')


admin.site.register(Xschools, XschoolsAdmin)
admin.site.register(Xsuser, XsuserAdmin)
