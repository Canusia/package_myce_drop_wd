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

app_name = 'instructor_drop_wd'

router = routers.DefaultRouter()
ROUTER_VS = {
    'class_sections': ClassSectionViewSet,
    'class_section/registrations': ClassRegistrationViewSet,
    'requests': DropWDRequestViewSet,
}

for router_key in ROUTER_VS.keys():
    router.register(
        router_key,
        ROUTER_VS[router_key],
        basename=app_name
    )

urlpatterns = [
    path(
        'api/',
        include(router.urls)
    ),
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
