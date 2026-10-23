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
                # a colleague's section (#12). And only in a role the settings
                # let start a request at all.
                from .scoping import (
                    INSTRUCTOR, HIGHSCHOOL_ADMIN, STUDENT,
                    registration_in_role_scope,
                    submitting_roles,
                )

                may_submit_as = submitting_roles(user)

                def own_signature(role):
                    if role in may_submit_as and \
                            registration_in_role_scope(user, role, instance.registration):
                        return 'Approved'
                    return 'Pending'

                # save(update_fields) rather than QuerySet.update(), so the
                # pre-approval is recorded in the request's history (#4).
                changed = []
                for needed, field, role in (
                    (DropWDRequest.needs_instructor_approval(), 'instructor_signature', INSTRUCTOR),
                    (DropWDRequest.needs_student_approval(), 'student_signature', STUDENT),
                    (DropWDRequest.needs_administrator_approval(), 'counselor_signature', HIGHSCHOOL_ADMIN),
                ):
                    if needed:
                        value = own_signature(role)
                        if getattr(instance, field) != value:
                            setattr(instance, field, value)
                            changed.append(field)
                if changed:
                    instance.save(update_fields=changed)

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
