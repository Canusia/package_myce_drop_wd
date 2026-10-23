"""
    Instructor URL Configuration
"""
from django.urls import path, include

from rest_framework import routers

from ..views import (
    requests,
    drop_request,
    do_bulk_action,
)

app_name = 'student_drop_wd'

urlpatterns = [
    path(
        'bulk_actions/',
        do_bulk_action,
        name='bulk_actions'),
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
]
