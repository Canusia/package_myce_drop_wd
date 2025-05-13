import uuid
from django.db import models
from django.db.models import JSONField

from mailer import send_mail, send_html_mail
from django.template import Context, Template
from django.conf import settings
from django.template.loader import get_template, render_to_string
from django.core.validators import validate_email

from .settings.drop_wd_email import drop_wd_email

from model_utils import FieldTracker

from cis.models.section import StudentRegistration
from cis.utils import model_as_HTML

class DropWDRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_on = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        'cis.CustomUser',
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )
    processed_by = models.ForeignKey(
        'cis.CustomUser',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='processed_by'
    )

    registration = models.ForeignKey('cis.StudentRegistration', on_delete=models.CASCADE)

    STATUS_OPTIONS = (
        ('requested', 'Requested'),
        # ('approved_instructor', 'Approved'),
        # ('not_approved_instructor', 'Not Approved'),
        ('processed', 'Processed')
        ('approved', 'Approved')
        ('not_approved', 'Not Approved')
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_OPTIONS,
        default='requested'
    )

    tracker = FieldTracker(fields=['status'])
    status_changed_on = JSONField(
        blank=True,
        null=True
    )

    note = models.TextField(
        blank=True,
        null=True
    )

    notes = JSONField(
        default=dict
    )

    instructor_note = models.TextField(
        blank=True,
        null=True
    )
    
    ce_note = models.TextField(
        blank=True,
        null=True
    )

    SIGNATURE_STATUS = [
        ('Not Needed', 'Not Needed'),
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Not Approved', 'Not Approved'),
    ]
    student_signature = models.CharField(
        max_length=50,
        choices=SIGNATURE_STATUS,
        default='Not Needed'
    )

    parent_signature = models.CharField(
        max_length=50,
        choices=SIGNATURE_STATUS,
        default='Not Needed'
    )

    instructor_signature = models.CharField(
        max_length=50,
        choices=SIGNATURE_STATUS,
        default='Not Needed'
    )

    counselor_signature = models.CharField(
        max_length=50,
        choices=SIGNATURE_STATUS,
        default='Not Needed'
    )

    class Meta:
        unique_together = ['registration']

    @property
    def needs_approval():
        ...

    @classmethod
    def needs_student_approval(cls):
        configs = drop_wd_email.from_db()

        if 'student' in configs.get('signatures_required_from', []):
            return True
        return False
    
    @classmethod
    def needs_parent_approval(cls):
        configs = drop_wd_email.from_db()

        if 'parent' in configs.get('signatures_required_from', []):
            return True
        return False
    
    def record_needs_parent_approval(self):
        if not DropWDRequest.needs_parent_approval():
            return False
        
        if self.parent_signature == 'Pending':
            return True
        return False
    
    def record_needs_student_approval(self):
        if not DropWDRequest.needs_student_approval():
            return False
        
        if self.student_signature == 'Pending':
            return True
        return False
    
    @classmethod
    def needs_instructor_approval(cls):
        configs = drop_wd_email.from_db()

        if 'instructor' in configs.get('signatures_required_from', []):
            return True
        return False
    
    def record_needs_instructor_approval(self):
        if not DropWDRequest.needs_instructor_approval():
            return False
        
        if self.instructor_signature == 'Pending':
            return True
        return False
    
    @classmethod
    def needs_administrator_approval(cls):
        configs = drop_wd_email.from_db()

        if 'highschool_admin' in configs.get('signatures_required_from', []):
            return True
        return False

    def record_needs_administrator_approval(self):
        if not DropWDRequest.needs_administrator_approval():
            return False
        
        if self.counselor_signature == 'Pending':
            return True
        return False
    
    @classmethod
    def can_instructor_submit_request(self):
        configs = drop_wd_email.from_db()

        if 'instructor' in configs.get('start_new_request', []):
            return True
        return False

    @classmethod
    def can_student_submit_request(self):
        configs = drop_wd_email.from_db()

        if 'student' in configs.get('start_new_request', []):
            return True
        return False
    
    @classmethod
    def can_administrator_submit_request(self):
        configs = drop_wd_email.from_db()

        if 'highschool_admin' in configs.get('start_new_request', []):
            return True
        return False
    
    @property
    def next_step(self):
        return ''
    
        if self.status == 'requested':
            return 'Awaiting Instructor Approval'
        
        if self.status == 'approved_instructor':
            return 'Pending Processing'

        if self.status == 'processed':
            return ''

    @property
    def sexy_status(self):
        for (key, value) in self.STATUS_OPTIONS:
            if key == self.status:
                return value
        return ''

    @property
    def get_status_history(self):
        result = ''
        if not self.status_changed_on:
            return f'<div class="detail_label">{self.created_on}</div><div class="">Marked as \'{self.sexy_status}\'</div>'

        for key, val in self.status_changed_on.items():
            result += f'<div class="detail_label">{key}</div><div class="">Marked as \'{val}\'</div>'
        return result

    @property
    def student_note(self):
        return self.notes.get('student_note', '')

    @property
    def parent_note(self):
        return self.notes.get('parent_note', '')
    
    @property
    def instructor_note(self):
        return self.notes.get('instructor_note', '')
    
    @property
    def counselor_note(self):
        return self.notes.get('counselor_note', '')
    
    @property
    def signatures(self):
        pass

    @property
    def has_student_signed(self):
        return True if self.student_signature else False

    @property
    def has_parent_signed(self):
        return True if self.parent_signature else False

    @property
    def has_instructor_signed(self):
        return True if self.instructor_signature else False

    @property
    def has_counselor_signed(self):
        return True if self.counselor_signature else False

    def send_processed_notification(self):

        instance = self
        email_settings = drop_wd_email.from_db()
        if email_settings.get('is_active') == 'No':
            return

        subject = email_settings.get('processed_email_subject')
        email_template = Template(email_settings['processed_email'])
        context = Context({
            'student_first_name': instance.registration.student.user.first_name,
            'student_last_name': instance.registration.student.user.last_name,
            'instructor_first_name': instance.registration.class_section.teacher.user.first_name,
            'instructor_last_name': instance.registration.class_section.teacher.user.last_name,
            'course_name': instance.registration.class_section.course,
            'request_status': instance.status,
            'registration_status': instance.registration.get_status,
            'ce_note': instance.ce_note if instance.ce_note else '',
            'term': instance.registration.class_section.term
        })

        text_body = email_template.render(context)
        to = []

        if 'student' in email_settings.get('notification_list', []):
            to.append(
                instance.registration.student.user.email
            )
        
        if 'parent' in email_settings.get('notification_list', []):
            # if instance.has_parent_signed:
                try:
                    if validate_email(instance.registration.student.parent_email):
                        to.append(
                            instance.registration.student.parent_email
                        )
                except:
                    ...

        if 'instructor' in email_settings.get('notification_list', []):
            try:
                if validate_email(instance.registration.class_section.teacher.user.email):
                    to.append(
                        instance.registration.class_section.teacher.user.email
                    )
            except:
                ...

        if 'highschool_admin' in email_settings.get('notification_list', []):
            try:

                if instance.registration.reviewer and validate_email(instance.registration.reviewer.user.email):
                    to.append(
                        instance.registration.reviewer.user.email
                    )
            except:
                ...
    
        if instance.created_by:
            if validate_email(instance.created_by.email) and instance.created_by.email not in to:
                to.append(instance.created_by.email)

        template = get_template('cis/email.html')
        html_body = template.render({
            'message': text_body
        })

        if getattr(settings, 'DEBUG', True) or email_settings.get('is_active') == 'Debug':
            to = ['kadaji@gmail.com']

        if to:
            send_html_mail(
                subject,
                text_body,
                html_body,
                settings.DEFAULT_FROM_EMAIL,
                to
            )

    def parent_approval_url(self):
        from django.urls import reverse_lazy
        from cis.utils import getDomain
        return getDomain() + str(reverse_lazy(
            'student_drop_wd:request_parent_signature',
            kwargs={
                'record_id': self.id
            }
        ))
    
    def request_parent_approval_notification(self):

        instance = self
        email_settings = drop_wd_email.from_db()
        if email_settings.get('is_active') == 'No':
            return

        subject = email_settings.get('pending_parent_approval_email_subject')
        email_template = Template(email_settings['pending_parent_approval_email'])

        context = Context({
            'student_first_name': instance.registration.student.user.first_name,
            'student_last_name': instance.registration.student.user.last_name,
            'instructor_first_name': instance.registration.class_section.teacher.user.first_name,
            'instructor_last_name': instance.registration.class_section.teacher.user.last_name,
            'course_name': instance.registration.class_section.course,
            'request_status': instance.status,
            'registration_status': instance.registration.get_status,
            'ce_note': instance.ce_note if instance.ce_note else '',
            'term': instance.registration.class_section.term,
            'request_approval_url': instance.parent_approval_url()
        })

        text_body = email_template.render(context)
        to = []

        if 'parent' in email_settings.get('notification_list', []):
                try:
                    if validate_email(instance.registration.student.parent_email):
                        to.append(
                            instance.registration.student.parent_email
                        )
                except:
                    ...

        template = get_template('cis/email.html')
        html_body = template.render({
            'message': text_body
        })

        if getattr(settings, 'DEBUG', True) or email_settings.get('is_active') == 'Debug':
            to = ['kadaji@gmail.com']

        if to:
            send_html_mail(
                subject,
                text_body,
                html_body,
                settings.DEFAULT_FROM_EMAIL,
                to
            )

    def send_received_notification(self):

        instance = self
        email_settings = drop_wd_email.from_db()
        if email_settings.get('is_active') == 'No':
            return
        
        # notify ce staff
        to = email_settings.get('email_address_to_cep').split(',')

        email_template = Template(email_settings['email_to_cep'])
        subject = email_settings.get('email_subject_to_cep')

        context = Context({
            'submitted_by_first_name': instance.created_by.first_name if instance.created_by else '-',
            'submitted_by_last_name': instance.created_by.last_name if instance.created_by else '-',
            'student_first_name': instance.registration.student.user.first_name,
            'student_last_name': instance.registration.student.user.last_name,
            'instructor_first_name': instance.registration.class_section.teacher.user.first_name,
            'instructor_last_name': instance.registration.class_section.teacher.user.last_name,
            'course_name': instance.registration.class_section.course,
            'term': instance.registration.class_section.term,
            'note': instance.note,
        })

        text_body = email_template.render(context)

        template = get_template('cis/email.html')
        html_body = template.render({
            'message': text_body
        })

        if getattr(settings, 'DEBUG', True) or email_settings.get('is_active') == 'Debug':
            to = ['kadaji@gmail.com']

        if to:
            send_html_mail(
                subject,
                text_body,
                html_body,
                settings.DEFAULT_FROM_EMAIL,
                to
            )
        
        # notify student
        email_template = Template(email_settings['processed_email'])
        subject = email_settings.get('processed_email_subject')
        
        to = []        

        if 'student' in email_settings.get('notification_list', []):
            to.append(
                instance.registration.student.user.email
            )
        
        if 'parent' in email_settings.get('notification_list', []):    
            try:
                if validate_email(instance.registration.student.parent_email):
                    to.append(
                        instance.registration.student.parent_email
                    )
            except:
                ...

        if 'instructor' in email_settings.get('notification_list', []):
            try:
                if validate_email(instance.registration.class_section.teacher.user.email):
                    to.append(
                        instance.registration.class_section.teacher.user.email
                    )
            except:
                ...
    
        if instance.created_by:
            if instance.created_by.email not in to:
                to.append(instance.created_by.email)

        context = Context({
            'submitted_by_first_name': instance.created_by.first_name if instance.created_by else '-',
            'submitted_by_last_name': instance.created_by.last_name if instance.created_by else '-',
            'student_first_name': instance.registration.student.user.first_name,
            'student_last_name': instance.registration.student.user.last_name,
            'instructor_first_name': instance.registration.class_section.teacher.user.first_name,
            'instructor_last_name': instance.registration.class_section.teacher.user.last_name,
            'course_name': instance.registration.class_section.course,
            'term': instance.registration.class_section.term,
            'note': instance.note,
        })

        text_body = email_template.render(context)

        template = get_template('cis/email.html')
        html_body = template.render({
            'message': text_body
        })

        if getattr(settings, 'DEBUG', True) or email_settings.get('is_active') == 'Debug':
            to = ['kadaji@gmail.com']

        if to:
            send_html_mail(
                subject,
                text_body,
                html_body,
                settings.DEFAULT_FROM_EMAIL,
                to
            )

    @property
    def approvals(self):
        result = ""
        result += f"Student Approval - {self.student_signature}<br>"
        result += f"Parent Approval - {self.parent_signature}<br>"
        result += f"Instructor Approval - {self.instructor_signature}<br>"
        result += f"Counselor Approval - {self.counselor_signature}<br>"

        return result
    
    def asHTML(self):
        format = [
            
            [
                {
                    'label': 'Term',
                    'field': 'registration.class_section.term'
                },
                {
                    'label': 'Course',
                    'field': 'registration.class_section.course'
                }
            ],
            [
                {
                    'label': 'Instructor',
                    'field': 'registration.class_section.teacher'
                }
            ],
            [
                {
                    'label': 'Submitted By',
                    'field': 'created_by'
                },
            ],
            [
                {
                    'label': 'Note',
                    'field': 'note'
                },
                'processed_by'
            ],
            [
                {
                    'label': 'Section #',
                    'field': 'registration.class_section.class_number'
                },
                {
                    'label': 'Status',
                    'field': 'sexy_status'
                }
            ],
            [
                {
                    'label': 'Status History',
                    'field': 'get_status_history'
                }
            ],
            [
                'student_signature',
                'student_note'
            ],
            [
                'parent_signature',
                'parent_note'
            ],
            [
                'instructor_signature',
                'instructor_note'
            ],
            [
                'counselor_signature',
                'counselor_note'
            ]
        ]
        return model_as_HTML(self, format)
