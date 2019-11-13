
from __future__ import unicode_literals

from django.db import models

# guangyaw modify for nid
from django.contrib.auth.models import User


class Xsuser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nid_linked = models.TextField(blank=True, null=True, default='default')
    ask_nid_link = models.TextField(blank=True, null=True, default='default')

    class Meta(object):
        app_label = 'school_id_login'


class Xschools(models.Model):
    xschool_id = models.TextField(blank=True, null=True, default='default_id')
    xschool_client = models.TextField(blank=True, null=True, default='default_client')
    return_uri = models.TextField(blank=True, null=True, default='default_uri')

    class Meta(object):
        app_label = 'school_id_login'
