from django.conf import settings

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.contrib.sites.models import Site

from django.template import Context, Template
from django.template.loader import get_template, render_to_string

from mailer import send_mail, send_html_mail

from drop_wd.settings.drop_wd_email import drop_wd_email
from cis.middleware import current_request

from drop_wd.models import DropWDRequest


@receiver(pre_save, sender=DropWDRequest)
def status_changed(sender, instance, **kwargs):
    """
    Registration status was updated, so update status_updated_on JSONField
    """
    from datetime import datetime

    previous_status = instance.tracker.previous('status')
    status = instance.status

    if previous_status != status:
        status_changed_on = instance.status_changed_on
        if not status_changed_on:
            status_changed_on = {}

        try:
            if current_request():
                user = current_request().user
            else:
                user = None
            
            instance.registration.student.add_note(
                createdby=user,
                note=f'Updating drop/wd request for {instance.registration.class_section} to {instance.sexy_status}',
                meta={
                    'type': 'public',
                    'registration_id': str(instance.registration.id)
                }
            )
        except Exception as e:
            print(e)

        status_changed_on[status + "_on"] = datetime.now().strftime('%m/%d/%Y %I:%M:%S %p')
        instance.status_changed_on = status_changed_on

        instance.send_processed_notification()
            
@receiver(post_save, sender=DropWDRequest)
def create_new_request(sender, instance, created, **kwargs):
    """
    Send email to CE office when submitted
    """
    if created:
        instance.send_received_notification()

        try:
            if current_request():
                request = current_request()
                user = request.user

                from cis.utils import user_has_instructor_role, user_has_student_role, user_has_highschool_admin_role

                if DropWDRequest.needs_instructor_approval():
                    if user_has_instructor_role(request.user):
                        signature_status = 'Approved'
                    else:
                        signature_status = 'Pending'

                    DropWDRequest.objects.filter(
                        id=instance.id
                    ).update(instructor_signature=signature_status)
                    
                if DropWDRequest.needs_student_approval():
                    if user_has_student_role(request.user):
                        signature_status = 'Approved'
                    else:
                        signature_status = 'Pending'

                    DropWDRequest.objects.filter(
                        id=instance.id
                    ).update(student_signature=signature_status)
                    
                if DropWDRequest.needs_administrator_approval():
                    if user_has_highschool_admin_role(request.user):
                        signature_status = 'Approved'
                    else:
                        signature_status = 'Pending'

                    DropWDRequest.objects.filter(
                        id=instance.id
                    ).update(counselor_signature=signature_status)
                    
            else:
                user = None
            
            instance.registration.student.add_note(
                createdby=user,
                note=f'Added drop/wd request for {instance.registration.class_section} to {instance.sexy_status}',
                meta={
                    'type': 'public',
                    'registration_id': str(instance.registration.id)
                }
            )
        except Exception as e:
            print(e)
