import json
from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from form_fields import fields as FFields

from cis.models.term import Term
from cis.models.section import ClassSection, StudentRegistration

from django.utils.safestring import mark_safe

from cis.forms.section import EditStudentRegistration

from cis.utils import (
    user_has_instructor_role,
    user_has_highschool_admin_role,
    user_has_student_role
)

from drop_wd.settings.drop_wd_email import drop_wd_email
from .models import DropWDRequest

class CEDropRequestForm(forms.Form):
    registration_ids = forms.MultipleChoiceField(
        required=False,
        label='Registration Records',
        widget=forms.CheckboxSelectMultiple,
        choices=[]
    )

    note = forms.CharField(
        required=True,
        label='Message to MyHSCP Office',
        help_text='',
        widget=forms.Textarea
    )

    action = forms.CharField(
        widget=forms.HiddenInput
    )
    
    def __init__(self, registration_ids=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # field_labels = {}
        # for field_name in self.fields:
        #     field = self.fields[field_name]

        #     field_label = {
        #         'label': field.label,
        #         'help_text': field.help_text
        #     }
        #     field_labels[field_name] = field_label

        # import json
        # print(json.dumps(field_labels))


        form_settings = drop_wd_email.from_db()
        try:
            form_labels = json.loads(form_settings.get('form_field_messages', '{}'))
            form_labels = form_labels.get('cedroprequestform', {})
        except:
            form_labels = {}

        for field_name in self.fields:
            field = self.fields[field_name]

            if form_labels.get(field_name):
                field_attr = form_labels.get(field_name, {})

                field.label = mark_safe(field_attr.get('label', ''))
                field.help_text = mark_safe(field_attr.get('help_text', ''))

        self.fields['action'].initial = kwargs.get('action', 'submit_drop_request')
        if registration_ids:
            registrations = StudentRegistration.objects.filter(
                id__in=registration_ids
            )

            registration_choices = []
            for registration in registrations:
                registration_choices.append(
                    (
                        registration.id,
                        f"{registration.student} - {registration.class_section} ({registration.sexy_status})"
                    )
                )
            self.fields['registration_ids'].choices = registration_choices
            self.fields['registration_ids'].initial = registration_ids
        else:
            registration_choices = []
            for regis_id in kwargs.get('data').getlist('registration_ids'):
                registration_choices.append(
                    (regis_id, regis_id)
                )

            self.fields['registration_ids'].choices = registration_choices
            self.fields['registration_ids'].required = False

    def save(self, request, commit=True):
        
        data = self.cleaned_data

        for regis_id in data.get('registration_ids'):
            registration = StudentRegistration.objects.get(pk=regis_id)
            try:
                drop_req = DropWDRequest()
                drop_req.registration = registration
                drop_req.note = data['note']

                drop_req.status = 'requested'
                drop_req.created_by = request.user
                drop_req.save()
            except:
                ...
                
        return drop_req
    
class EditDropWDRequestForm(EditStudentRegistration, forms.Form):
    request_status = forms.ChoiceField(
        choices=DropWDRequest.STATUS_OPTIONS,
        label='Request Status',
        help_text='When marked as "Processed" notifications will be automatically sent.'
    )

    ce_note = forms.CharField(
        required=False,
        label='Public Note',
        help_text='This might be sent in the notification',
        widget=forms.Textarea
    )

    action = forms.CharField(
        widget=forms.HiddenInput
    )

    def __init__(self, record, *args, **kwargs):
        student_registration = StudentRegistration.objects.get(
            pk=record.registration.id
        )
        super().__init__(student_registration, *args, **kwargs)
        self.fields['status'].label = 'Registration Status'
        self.fields['action'].initial = 'update_drop_wd_request'

        self.fields['request_status'].initial = record.status
        self.fields['ce_note'].initial = record.ce_note

        self.fields['status'].help_text = 'Update registration status'

    def save(self, request, record):
        student_registration = StudentRegistration.objects.get(
            pk=record.registration.id
        )
        student_registration = super().save(student_registration)

        record.status = self.cleaned_data['request_status']
        record.ce_note = self.cleaned_data.get('ce_note')
        
        record.processed_by = request.user
        record.save()

        return record

from cis.utils import YES_NO_SELECT_OPTIONS
class RequestReviewForm(forms.Form):
    review_decision = forms.ChoiceField(
        choices=YES_NO_SELECT_OPTIONS,
        required=True,
        label='Do you approve this request?'
    )

    action = forms.CharField(
        widget=forms.HiddenInput,
        initial='review_request'
    )

    note = forms.CharField(
        widget=forms.Textarea,
        required=False,
        help_text='This will be shared with the student and the dual enrollment staff',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # field_labels = {}
        # for field_name in self.fields:
        #     field = self.fields[field_name]

        #     field_label = {
        #         'label': field.label,
        #         'help_text': field.help_text
        #     }
        #     field_labels[field_name] = field_label

        # import json
        # print(json.dumps(field_labels))


        form_settings = drop_wd_email.from_db()
        try:
            form_labels = json.loads(form_settings.get('form_field_messages', '{}'))
            form_labels = form_labels.get('requestreviewform', {})
        except:
            form_labels = {}

        for field_name in self.fields:
            field = self.fields[field_name]

            if form_labels.get(field_name):
                field_attr = form_labels.get(field_name, {})

                field.label = mark_safe(field_attr.get('label', ''))
                field.help_text = mark_safe(field_attr.get('help_text', ''))

    def save(self, request, record):
        data = self.cleaned_data

        if data.get('review_decision') == '1':
            status = 'Approved'
        else:
            status = 'Not Approved'

        if not record.notes:
            record.notes = {}

        if user_has_instructor_role(request.user):
            record.instructor_signature = status
            record.notes['instructor_note'] = data.get('note', '')

        elif user_has_highschool_admin_role(request.user):
            record.counselor_signature = status
            record.notes['counselor_note'] = data.get('note', '')

        elif user_has_student_role(request.user):
            record.student_signature = status
            record.notes['student_note'] = data.get('note', '')

        record.save()
        return record

class DropWDSignatureForm(forms.Form):
    id = forms.CharField(
        widget=forms.HiddenInput
    )

    signature_type = forms.CharField(
        widget=forms.HiddenInput
    )

    signature = FFields.SignatureField(
        label='Signature',
        required=False,
        error_messages={
            'required':'Please sign in the box'
        },
        widget=FFields.SignatureWidget
    )

    def save(self, request, record):
        data = self.cleaned_data
        if data['signature_type'] == 'parent':
            record.parent_signature = data['signature']
        elif data['signature_type'] == 'student':
            record.student_signature = data['signature']

        record.save()
        return record


class DropWDRequestForm(forms.Form):
    term = forms.ModelChoiceField(
        queryset=None
    )

    class_section = forms.ModelChoiceField(
        queryset=None,
        label='Class Section',
        empty_label="Select Term"
    )

    registration = forms.ModelChoiceField(
        queryset=None,
        label='Student',
        empty_label="Select a Class Section"
    )

    note = forms.CharField(
        required=True,
        label='Message to CE/Dual Enroll Office',
        help_text='This information will be shared with the instructor, school counselor and dual enroll office.',
        widget=forms.Textarea
    )

    # signature = FFields.SignatureField(
    #     label='Your Signature',
    #     required=True,
    #     error_messages={
    #         'required':'Please sign in the box'
    #     },
    #     widget=FFields.SignatureWidget
    # )

    def __init__(self, class_section=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # field_labels = {}
        # for field_name in self.fields:
        #     field = self.fields[field_name]

        #     field_label = {
        #         'label': field.label,
        #         'help_text': field.help_text
        #     }
        #     field_labels[field_name] = field_label

        # import json
        # print(json.dumps(field_labels))


        form_settings = drop_wd_email.from_db()
        try:
            form_labels = json.loads(form_settings.get('form_field_messages', '{}'))
            form_labels = form_labels.get('noncedroprequestform', {})
        except:
            form_labels = {}

        for field_name in self.fields:
            field = self.fields[field_name]

            if form_labels.get(field_name):
                field_attr = form_labels.get(field_name, {})

                field.label = mark_safe(field_attr.get('label', ''))
                field.help_text = mark_safe(field_attr.get('help_text', ''))

        self.fields['term'].queryset = Term.objects.all()
        self.fields['class_section'].queryset = ClassSection.objects.none()
        self.fields['registration'].queryset = StudentRegistration.objects.none()

        if class_section:
            self.fields['term'].initial = class_section.term
            self.fields['class_section'].queryset = ClassSection.objects.filter(pk=class_section.id)
            self.fields['class_section'].initial = class_section.id

            self.fields['registration'].queryset = StudentRegistration.objects.filter(
                class_section=class_section
            ).order_by('student__user__last_name')
            self.fields['registration'].empty_label = 'Select'

        if kwargs.get('data'):
            if self.data.get('class_section'):
                class_section = self.data['class_section']
                self.fields['class_section'].queryset = ClassSection.objects.filter(
                    id=class_section
                )

            registration = self.data['registration']
            self.fields['registration'].queryset = StudentRegistration.objects.filter(
                id=registration
            )

    def clean_registration(self):
        regis = self.cleaned_data.get('registration')

        if DropWDRequest.objects.filter(
            registration=regis
        ).exists():
            raise ValidationError('A request already exists for the selected registration')

        return regis

    def save(self, request):
        drop_req = DropWDRequest()
        data = self.cleaned_data

        drop_req.registration = data['registration']
        drop_req.note = data['note']

        # if user_has_highschool_admin_role(request.user):
        #     drop_req.counselor_signature = data['signature']
        # elif user_has_instructor_role(request.user):
        #     drop_req.instructor_signature = data['signature']

        drop_req.status = 'requested'
        drop_req.created_by = request.user
        drop_req.save()

        return drop_req

from django.forms import ModelChoiceField

class StudentRegistrationChoiceField(ModelChoiceField):

    def label_from_instance(self, obj):
        return f'{obj.class_section.term}, {obj.class_section.course.name} / {obj.class_section.class_number} ({obj.get_status})'

class StudentDropWDRequestForm(DropWDRequestForm, forms.Form):
    
    def __init__(self, student, *args, **kwargs):
        super().__init__(class_section=None, *args, **kwargs)

        del self.fields['class_section']
        del self.fields['term']

        self.fields['registration'] = StudentRegistrationChoiceField(
            label='Class Registrations',
            queryset = StudentRegistration.objects.filter(
                student=student
            ).order_by('-created_on')
        )

        # field_labels = {}
        # for field_name in self.fields:
        #     field = self.fields[field_name]

        #     field_label = {
        #         'label': field.label,
        #         'help_text': field.help_text
        #     }
        #     field_labels[field_name] = field_label

        # import json
        # print(json.dumps(field_labels))


        form_settings = drop_wd_email.from_db()
        try:
            form_labels = json.loads(form_settings.get('form_field_messages', '{}'))
            form_labels = form_labels.get('studentdroprequestform', {})
        except:
            form_labels = {}

        for field_name in self.fields:
            field = self.fields[field_name]

            if form_labels.get(field_name):
                field_attr = form_labels.get(field_name, {})

                field.label = mark_safe(field_attr.get('label', ''))
                field.help_text = mark_safe(field_attr.get('help_text', ''))

    def save(self, request):
        req = DropWDRequest()
        data = self.cleaned_data

        req.registration = data.get('registration')
        req.note = data.get('note')

        # req.student_signature = data.get('signature')
        req.created_by = request.user

        req.save()

        return req