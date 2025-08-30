"""
    Instructor URL Configuration
"""
from django.urls import path, include

from rest_framework import routers

from ..views import (
    drop_summary_view,
    requests,
    drop_request,
    delete_record,
    do_bulk_action,
    send_parent_email,
    drop_summary_view
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
    path(
        'bulk_actions/',
        do_bulk_action,
        name='bulk_actions'
    ),
    
    path('send_parent_email/<uuid:record_id>/', 
        send_parent_email, 
        name='send_parent_email'),
        
    path('ce/drop_wd/requests/summary/', 
         drop_summary_view, 
         name='drop_summary_view'),    
]