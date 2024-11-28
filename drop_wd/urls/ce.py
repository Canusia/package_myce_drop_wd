"""
    Instructor URL Configuration
"""
from django.urls import path, include

from rest_framework import routers

from ..views import (
    requests,
    drop_request,
    delete_record
)

app_name = 'ce_drop_wd'

urlpatterns = [
    path(
        'requests/',
        requests,
        name='requests'
    ),
    path(
        'request/<uuid:record_id>',
        drop_request,
        name='request'
    ),
    path(
        'request/delete/<uuid:record_id>',
        delete_record,
        name='delete_record'
    ),
]
