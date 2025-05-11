"""
    Instructor URL Configuration
"""
from django.urls import path, include

from rest_framework import routers

from ..views import (
    requests,
    drop_request,
    parent_signature
)

app_name = 'student_drop_wd'

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
        'request/parent_signature/<uuid:record_id>',
        parent_signature,
        name='request_parent_signature'
    ),

]
