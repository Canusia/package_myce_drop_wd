"""Drop/WD Requests Summary report (#6): request counts by term, academic
year, high school and course (plus instructor and status if asked), one
worksheet per breakdown.

Registered from the REPORTS manifest in apps.py; report.ReportScheduler.run
imports `<app>.reports.drop_wd_summary.drop_wd_summary` and calls run().
"""
import datetime
import io

import xlsxwriter
from django import forms
from django.core.files.base import ContentFile
from django.urls import reverse_lazy

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from cis.models.term import AcademicYear, Term
from cis.utils import user_has_cis_role, user_has_highschool_admin_role

from ..models import DropWDRequest
from ..summary import BREAKDOWNS, breakdowns

DEFAULT_BREAKDOWNS = ['term', 'academic_year', 'highschool', 'course']


def scoped_requests(user, term_ids=None, academic_year_ids=None, status=None):
    """Requests the report covers for `user`: CE staff all, an HS admin only
    their schools' students, anyone else none. The report runs in a task with
    no request, so the scope is re-derived from the requester here."""
    records = DropWDRequest.objects.all()
    if user is None or not user_has_cis_role(user):
        if user is not None and user_has_highschool_admin_role(user):
            records = records.filter(
                registration__student__highschool__id__in=list(
                    user.get_highschools_for_admin()))
        else:
            return records.none()

    if term_ids:
        records = records.filter(registration__class_section__term__id__in=term_ids)
    if academic_year_ids:
        records = records.filter(
            registration__class_section__term__academic_year__id__in=academic_year_ids)
    if status:
        records = records.filter(status__in=status)
    return records


def build_workbook(tables):
    """xlsx bytes: one sheet per breakdown table."""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    bold = workbook.add_format({'bold': True})
    for table in tables:
        sheet = workbook.add_worksheet(table['name_label'][:31])
        headers = [table['name_label'], 'Total', 'Requested', 'Processed', '% of Total']
        sheet.write_row(0, 0, headers, bold)
        for i, row in enumerate(table['rows'], start=1):
            sheet.write_row(i, 0, [row['name'], row['total'], row['requested'],
                                   row['processed'], row['pct']])
        sheet.set_column(0, 0, 40)
    workbook.close()
    return output.getvalue()


def _ids(values):
    """Task data is dict(request.POST): every value is a list of strings."""
    if values is None or isinstance(values, (str, int)):
        values = [values] if values not in (None, '') else []
    return [str(getattr(v, 'pk', v)) for v in values if v not in (None, '')]


class drop_wd_summary(forms.Form):

    terms = forms.ModelMultipleChoiceField(
        queryset=None,
        label='Term(s)',
        required=False,
        help_text='Leave empty for all terms.',
    )

    academic_years = forms.ModelMultipleChoiceField(
        queryset=None,
        label='Academic Year(s)',
        required=False,
        help_text='Leave empty for all academic years.',
    )

    status = forms.MultipleChoiceField(
        choices=DropWDRequest.STATUS_OPTIONS,
        required=False,
    )

    breakdowns = forms.MultipleChoiceField(
        choices=[(key, title) for key, title, _paths, _label in BREAKDOWNS],
        initial=DEFAULT_BREAKDOWNS,
        widget=forms.CheckboxSelectMultiple,
        label='Summarize by',
    )

    request = None

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request

        self.helper = FormHelper()
        self.helper.attrs = {'target': '_blank'}
        self.helper.form_method = 'POST'
        self.helper.add_input(Submit('submit', 'Generate Summary'))
        if request:
            self.helper.form_action = reverse_lazy(
                'report:run_report', args=[request.GET.get('report_id')])

        self.fields['terms'].queryset = Term.objects.all().order_by('-code')
        self.fields['academic_years'].queryset = AcademicYear.objects.all().order_by('-name')

    def run(self, task, data):
        from cis.backends.storage_backend import PrivateMediaStorage

        records = scoped_requests(
            task.created_by,
            term_ids=_ids(data.get('terms')),
            academic_year_ids=_ids(data.get('academic_years')),
            status=[v for v in (data.get('status') or []) if v] or None,
        )
        keys = [k for k in (data.get('breakdowns') or []) if k] or DEFAULT_BREAKDOWNS
        content = build_workbook(breakdowns(records, keys=keys))

        file_name = ('drop_wd_requests_summary_'
                     + datetime.datetime.now().strftime('%m-%d-%Y') + '.xlsx')
        storage = PrivateMediaStorage()
        path = storage.save(f'reports/{task.id}/{file_name}', ContentFile(content))
        return storage.url(path)
