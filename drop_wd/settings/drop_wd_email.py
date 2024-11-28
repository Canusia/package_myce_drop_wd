import json
from django import forms
from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError

from django.utils.safestring import mark_safe

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.models.term import Term, AcademicYear
from cis.models.settings import Setting

from cis.validators import validate_email_list, validate_html_short_code, validate_json

class SettingForm(forms.Form):

    STATUS_OPTIONS = [
        ('', 'Select'),
        ('Yes', 'Yes'),
        ('No', 'No'),
        ('Debug', 'Debug'),
    ]

    is_active = forms.ChoiceField(
        choices=STATUS_OPTIONS,
        label='Enabled',
        help_text='',
        widget=forms.Select(attrs={'class': 'col-md-4 col-sm-12'}))

    start_new_request = forms.MultipleChoiceField(
        choices=[
            ('student', 'Student'),
            ('instructor', 'Instructor'),
            ('highschool_admin', 'High School Administrator'),
        ],
        required=False,
        label='Who can start new Request',
        widget=forms.CheckboxSelectMultiple
    )

    intro = forms.CharField(
        max_length=None,
        widget=forms.Textarea,
        help_text='Displayed before Drop/WD Request form. <a href="#" class="float-right" onClick="do_bulk_action(\'drop_wd_email\', \'intro\')" >See Preview</a>',
        label="Intro."
    )
    
    submit_new_intro = forms.CharField(
        max_length=None,
        widget=forms.Textarea,
        help_text='Displayed in the Submit new tab of Drop/WD Request form. <a href="#" class="float-right" onClick="do_bulk_action(\'drop_wd_email\', \'intro\')" >See Preview</a>',
        label="Submit New Request - Intro."
    )
    
    signatures_required_from = forms.MultipleChoiceField(
        choices=[
            ('student', 'Student'),
            ('instructor', 'Instructor'),
            ('highschool_admin', 'High School Administrator'),
        ],
        required=False,
        label='Who needs to approve a New Request',
        widget=forms.CheckboxSelectMultiple
    )
    
    notification_list = forms.MultipleChoiceField(
        choices=[
            ('student', 'Student'),
            ('parent', 'Parent'),
            ('instructor', 'Instructor'),
            ('highschool_admin', 'High School Administrator'),
        ],
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Who should be notified?',
        help_text='They will receive notification when request is submitted, and when it is marked as processed. The person submitting the request will also receive the notification.'
    )

    # use for different status labels of request
    processed_email_subject = forms.CharField(
        max_length=200,
        help_text='',
        label="Request Submitted/Processed - Email Subject")

    processed_email = forms.CharField(
        max_length=None,
        widget=forms.Textarea,
        validators=[validate_html_short_code],
        help_text='Email template sent when request is submitted and updated. Customize with {{instructor_first_name}}, {{instructor_last_name}}, {{student_first_name}}, {{student_last_name}}, {{course_name}}, {{term}}, {{ce_note}}, {{registration_status}}, {{request_status}}. <a href="#" class="float-right" onClick="do_bulk_action(\'drop_wd_email\', \'processed_email\')" >See Preview</a>',
        label="Request Submitted/Processed - Email"
    )

    email_address_to_cep = forms.CharField(
        max_length=200,
        required=False,
        help_text='Who should be notified when a new request is submitted. Comma separated',
        label="To CE Office - Email Address",
        validators=[validate_email_list]
    )
    email_subject_to_cep = forms.CharField(
        max_length=200,
        help_text='',
        label="Request Received - Email Subject")

    email_to_cep = forms.CharField(
        max_length=None,
        label='Request Received - Email',
        widget=forms.Textarea,
        validators=[validate_html_short_code],
        help_text='Email template sent to CE Office. Customize with {{note}}, {{submitted_by_first_name}}, {{submitted_by_last_name}}, {{instructor_first_name}}, {{instructor_last_name}}, {{student_first_name}}, {{student_last_name}}, {{course_name}}, {{term}}. <a href="#" class="float-right" onClick="do_bulk_action(\'drop_wd_email\', \'email_to_cep\')" >See Preview</a>'
    )

    form_field_messages = forms.CharField(
        max_length=None,
        validators=[validate_json],
        widget=forms.Textarea,
        help_text='Form Field Labels & Help Text',
        label="Request Forms Field Labels")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _to_python(self):
        """
        Return dict of form elements from $_POST
        """
        return {
            'is_active': self.cleaned_data['is_active'],
            'start_new_request': self.cleaned_data['start_new_request'],
            'intro': self.cleaned_data['intro'],
            'submit_new_intro': self.cleaned_data['submit_new_intro'],
            'signatures_required_from': self.cleaned_data['signatures_required_from'],
            
            'notification_list': self.cleaned_data['notification_list'],
            'processed_email_subject': self.cleaned_data['processed_email_subject'],
            'processed_email': self.cleaned_data['processed_email'],
            
            'email_address_to_cep': self.cleaned_data['email_address_to_cep'],
            'email_subject_to_cep': self.cleaned_data['email_subject_to_cep'],
            'email_to_cep': self.cleaned_data['email_to_cep'],

            'form_field_messages': self.cleaned_data['form_field_messages'],
            
        }


class drop_wd_email(SettingForm):
    key = str(__name__)
    
    title = 'Drop/WD Requests'
    category = [
        1,
    ]

    def preview(self, request, field_name):

        from django.template.loader import get_template, render_to_string
        from django.template import Context, Template
        from django.shortcuts import render, get_object_or_404

        email_settings = self.from_db()

        if field_name == 'intro':
            template = 'drop_wd/student/requests.html'
            page_settings = self.from_db()
            
            return render(
                request,
                template,
                {
                    'drop_wd_intro': page_settings.get('intro'),
                    'submit_new_intro': page_settings.get('submit_new_intro'),
                },
            )
        if field_name == 'email_to_cep':
            email = email_settings.get('email_to_cep')
            subject = email_settings.get('email_subject_to_cep')
        if field_name == 'processed_email':
            email = email_settings.get('processed_email')
            subject = email_settings.get('processed_email_subject')

        email_template = Template(email)
        context = Context({
            'instructor_first_name': request.user.first_name,
            'instructor_last_name': request.user.last_name,
            'submitted_by_first_name': request.user.first_name,
            'submitted_by_last_name': request.user.last_name,
            'student_first_name': 'FirstName',
            'student_last_name': 'LastName',
            'note': 'Note',
            'course_name': 'Course',
            'term': "Term",
            'earned_pd_hour': "100",
            'start_date_time': "12/01/1977 05:43",
            'end_date_time': "11/18/2018 12:22",
            'event_type': "Event Type",
            'delivery_mode': "Delivery Mode",
            'pd_letter_url': "https://pd_letter_url",
        })

        text_body = email_template.render(context)
        
        return render(
            request,
            'cis/email.html',
            {
                'message': text_body
            }
        )


    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.request = request
        self.helper = FormHelper()
        self.helper.attrs = {'target':'_blank'}
        self.helper.form_method = 'POST'
        self.helper.form_action = reverse_lazy(
            'setting:run_record', args=[request.GET.get('report_id')])
        self.helper.add_input(Submit('submit', 'Save Setting'))

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


        form_settings = self.from_db()
        try:
            form_labels = json.loads(form_settings.get('form_field_messages', '{}'))
            form_labels = form_labels.get('settingsform', {})
        except:
            form_labels = {}

        for field_name in self.fields:
            field = self.fields[field_name]

            if form_labels.get(field_name):
                field_attr = form_labels.get(field_name, {})

                field.label = mark_safe(field_attr.get('label', ''))
                field.help_text = mark_safe(field_attr.get('help_text', ''))

    def install(self):
        defaults = {'is_active': 'Yes', 'email_to_cep': 'Change this in Settings -> Misc -> Subject', 'processed_email': 'Change this in Settings -> Misc -> Subject', 'email_address_to_cep': 'kadaji@gmail.com', 'email_subject_to_cep': 'Change this in Settings -> Misc -> Subject', 'processed_email_subject': 'Change this in Settings -> Misc -> Subject'}

        try:
            setting = Setting.objects.get(key=self.key)
        except Setting.DoesNotExist:
            setting = Setting()
            setting.key = self.key

        setting.value = defaults
        setting.save()

    @classmethod
    def from_db(cls):
        try:
            setting = Setting.objects.get(key=cls.key)
            return setting.value
        except Setting.DoesNotExist:
            return {}

    def run_record(self):
        try:
            setting = Setting.objects.get(key=self.key)
        except Setting.DoesNotExist:
            setting = Setting()
            setting.key = self.key

        setting.value = self._to_python()
        setting.save()

        return JsonResponse({
            'message': 'Successfully saved settings',
            'status': 'success'})
