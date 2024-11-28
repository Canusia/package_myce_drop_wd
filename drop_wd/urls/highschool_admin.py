"""
    Instructor URL Configuration
"""
from django.urls import path, include

from rest_framework import routers

from ..views import (
    submit_request,
    requests,
    drop_request,
    ClassSectionViewSet,
    ClassRegistrationViewSet,
    DropWDRequestViewSet,
    do_bulk_action
)

app_name = 'highschool_admin_drop_wd'

urlpatterns = [
    path(
        'submit_request/',
        submit_request,
        name='submit_request'),
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
