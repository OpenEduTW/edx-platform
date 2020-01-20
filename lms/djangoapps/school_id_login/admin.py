# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin
from school_id_login.models import Xschools, Xsuser


class XschoolsAdmin(admin.ModelAdmin):
    list_display = ('xschool_id', 'xschool_client',"xschool_secret", 'return_uri')
    ordering = ("xschool_id",)


class XsuserAdmin(admin.ModelAdmin):
    list_display = ('user', 'nid_linked', 'ask_nid_link', 'oid_linked', 'ask_oid_link')
    search_fields = ("user",)
    ordering = ("user",)


admin.site.register(Xschools, XschoolsAdmin)
admin.site.register(Xsuser, XsuserAdmin)
