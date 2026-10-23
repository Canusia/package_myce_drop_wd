from django.conf import settings

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.contrib.sites.models import Site

from django.template import Context, Template
from django.template.loader import get_template, render_to_string

from mailer import send_mail, send_html_mail


from cis.middleware import current_request

from .models import DropWDRequest
from .settings.drop_wd_email import drop_wd_email

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

        if status == 'processed':
            instance.send_processed_notification()
            
@receiver(post_save, sender=DropWDRequest)
def create_new_request(sender, instance, created, **kwargs):
    """
    Send email to CE office when submitted
    """
    if created:
        # Notifications are a side-effect of saving the request and must never
        # break the save itself (the row is already committed at post_save time).
        try:
            instance.send_received_notification()
        except Exception as e:
            print(e)

        try:
            if current_request():
                request = current_request()
                user = request.user

                # A submitter's own signature is pre-approved only where they
                # could have given it: as instructor on a section they teach,
                # as counselor for a student at their schools, as the student
                # on their own registration. Not the union of their roles, or a
                # teacher who is also an HS admin would sign as instructor for
                # a colleague's section (#12).
                from .scoping import (
                    INSTRUCTOR, HIGHSCHOOL_ADMIN, STUDENT,
                    registration_in_role_scope,
                )

                def own_signature(role):
                    if registration_in_role_scope(user, role, instance.registration):
                        return 'Approved'
                    return 'Pending'

                if DropWDRequest.needs_instructor_approval():
                    DropWDRequest.objects.filter(
                        id=instance.id
                    ).update(instructor_signature=own_signature(INSTRUCTOR))

                if DropWDRequest.needs_student_approval():
                    DropWDRequest.objects.filter(
                        id=instance.id
                    ).update(student_signature=own_signature(STUDENT))

                if DropWDRequest.needs_administrator_approval():
                    DropWDRequest.objects.filter(
                        id=instance.id
                    ).update(counselor_signature=own_signature(HIGHSCHOOL_ADMIN))

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
