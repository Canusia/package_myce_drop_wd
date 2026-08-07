import io, csv, xlsxwriter, datetime

from django import forms
from django.urls import reverse_lazy
from django.forms import ValidationError
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from django.utils.encoding import force_str
from django.core.files.base import ContentFile, File
from django.template.loader import get_template

from cis.backends.storage_backend import PrivateMediaStorage
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.utils import (
    export_to_excel, user_has_cis_role,
    user_has_highschool_admin_role, get_field
)

from cis.models.highschool import HighSchool
from cis.models.term import Term
from drop_wd.models import DropWDRequest

class drop_wd_requests(forms.Form):

    terms = forms.ModelMultipleChoiceField(
        queryset=None,
        label='Term(s)'
    )

    status = forms.MultipleChoiceField(
        choices=DropWDRequest.STATUS_OPTIONS,
        required=False,
    )

    highschools = forms.ModelMultipleChoiceField(
        queryset=None,
        label='High School(s)',
        required=False
    )


    roles = []
    request = None
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.request = request

        self.helper = FormHelper()
        self.helper.attrs = {'target':'_blank'}
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', 'Generate Export'))

        if request:
            self.helper.form_action = reverse_lazy(
                'report:run_report', args=[request.GET.get('report_id')]
            )
        
        self.fields['terms'].queryset = Term.objects.all().order_by('label')

        highschools = HighSchool.objects.filter(
            status__iexact='Active'
        ).order_by('name')

        if request:
            self.roles = request.user.get_roles()

            if 'ce' not in self.roles and 'highschool_admin' in self.roles:
                highschools = highschools.filter(
                    id__in=request.user.get_highschools_for_admin()
                )

        self.fields['highschools'].queryset = highschools

    def run(self, task, data):
        term_ids = data.get('terms', None)
        highschool_ids = data.get('highschools', None)

        records = DropWDRequest.objects.filter(
            registration__class_section__term__id__in=term_ids
        )
        
        # The form is not re-instantiated here (no request), so the queryset
        # gate in __init__ cannot be relied on — re-apply it against the user
        # who requested the report.
        requested_by = task.created_by
        if not user_has_cis_role(requested_by) and \
                user_has_highschool_admin_role(requested_by):
            allowed_ids = [
                str(id) for id in requested_by.get_highschools_for_admin()
            ]
            highschool_ids = [
                id for id in (highschool_ids or [])
                if str(id) in allowed_ids
            ] or allowed_ids

            if not highschool_ids:
                # HS admin with no assigned schools sees nothing, rather than
                # falling through the `if highschool_ids` guard unfiltered.
                records = records.none()

        if highschool_ids:
            records = records.filter(
                registration__student__highschool__id__in=highschool_ids
            )

        if data.get('status'):
            records = records.filter(
                status__in=data.get('status')
            )

        file_name = "drop_wd_requests" + str(datetime.datetime.now().strftime('%m-%d-%Y')) + ".csv"
        fields = {
            # 'pk': 'HighSchoolMemberPositionID',
            'created_on': 'Created On',
            'created_by': 'Submitted By',
            'status': 'Request Status',
            'note': 'Note added by Submitter',
            'registration.student': 'Student',
            'registration.student.user.email': 'Student Email',
            'registration.student.user.psid': 'EMPLID',
            'registration.class_section.class_number': 'CRN',
            'registration.class_section.term': 'Term',
            'registration.class_section.teacher': 'Teacher',
            'registration.class_section.teacher.user.email': 'Teacher Email',
            'registration.student.highschool.name': 'High School',
            'registration.student.highschool.hs_type_display': 'School Type',
            'registration.class_section.highschool.name': 'Class Section High School',
            'registration.status': 'Registration Status',

            'processed_by': 'Processed By',
            'ce_note': 'Note added by Processor',
            'id': 'Request ID',

            'student_signature': "Student Approval",
            'instructor_signature': "Instructor Approval",
            'counselor_signature': "Counselor Approval",

            'student_note': 'Student Note',
            'instructor_note': 'Instructor Note',
            'counselor_note': 'Counselor Note',
        }

        http_response = export_to_excel(
            file_name,
            records,
            fields
        )

        path = "reports/" + str(task.id) + "/" + file_name
        media_storage = PrivateMediaStorage()

        path = media_storage.save(path, ContentFile(http_response.content))
        path = media_storage.url(path)

        return path