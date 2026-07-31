"""Shared config builder for the DropWDRequest DataTable.

Consumed by the portal Drop/WD requests page (instructor, and the student /
highschool_admin templates that {% include %} it) and by the CE table
(`drop_wd/ce/requests_table.html`, itself included by seven cis detail-page
tabs through the {% drop_wd_requests_table %} inclusion tag).

The JS counterpart is drop_wd/staticfiles/drop_wd/js/requests_table.js — the
two registries (header HTML here, column defs there) share key namespaces.

This module is the *packaged default*. A tenant may override it by adding
`myce_tenant_configs/services/drop_wd_requests_table.py`; see
`drop_wd.services.get_requests_table_config`.
"""
from ._base import build_table_config


# <th> markup paired with each JS column key. data-data / data-name are real
# ORM paths consumed by rest_framework_datatables for ordering and search —
# changing them raises FieldError at request time.
COLUMN_HEADER_HTML = {
    'select':         '<th data-data="id" data-name="id"></th>',
    'submitted_on':   '<th data-data="created_on" data-name="created_on">Submitted On</th>',
    'submitted_by':   '<th data-data="created_by" data-name="created_by">Submitted By</th>',
    'term':           '<th data-data="registration.class_section.term.code" data-name="registration.class_section.term.code">Term</th>',
    'student':        '<th data-data="registration.student.user.last_name" data-name="registration.student.user.last_name">Student</th>',
    'course':         '<th data-data="registration.class_section.course.name" data-name="registration.class_section.course.name">Course</th>',
    'class_number':   '<th data-data="registration.class_section.class_number" data-name="registration.class_section.class_number">Class No.</th>',
    'section_number': '<th data-data="registration.class_section.section_number" data-name="registration.class_section.section_number">Section #</th>',
    'approvals':      '<th data-data="approvals" data-name="approvals">Approvals</th>',
    'status':         '<th data-data="status" data-name="status">Status</th>',
    'edit_action':    '<th data-data="id" data-name="id"><span class="sr-only">Actions</span></th>',
}


# The CE table's <thead> differs from the portal one: it carries searchable="1"
# markers (its column-search row is cloned from the header and reads them) and
# a couple of different labels. data-data / data-name are copied VERBATIM from
# the pre-refactor drop_wd/ce/requests_table.html — note the instructor column's
# data-name is a two-field comma list.
CE_COLUMN_HEADER_HTML = dict(COLUMN_HEADER_HTML, **{
    'term':           '<th searchable="1" data-data="registration.class_section.term.code" data-name="registration.class_section.term.code">Term</th>',
    'highschool':     '<th searchable="1" data-data="registration.student.highschool.name" data-name="registration.student.highschool.name">High School</th>',
    'student':        '<th searchable="1" data-data="registration.student.user.last_name" data-name="registration.student.user.last_name">Student</th>',
    'course':         '<th searchable="1" data-data="registration.class_section.course.name" data-name="registration.class_section.course.name">Course</th>',
    'class_number':   '<th searchable="1" data-data="registration.class_section.class_number" data-name="registration.class_section.class_number">CRN / Class #</th>',
    'section_number': '<th searchable="1" data-data="registration.class_section.section_number" data-name="registration.class_section.section_number">Section #</th>',
    'instructor':     '<th searchable="1" data-data="registration.class_section.teacher.user.last_name" data-name="registration.class_section.teacher.user.last_name,registration.class_section.teacher.user.first_name">Instructor</th>',
    'approvals':      '<th searchable="0" data-data="approvals" data-name="approvals">Approvals</th>',
    'status':         '<th searchable="1" data-data="status" data-name="status">Status</th>',
})


# The CE table has always talked to the instructor endpoint. Phase 3 makes it a
# parameter; it does not move the endpoint.
CE_DEFAULT_API_URL = '/instructor/drop_wd/api/requests/?format=datatables'


# cis detail-page tab `type` -> the query param the CE table scopes on.
# Copied from the pre-refactor template's {% if type == ... %} ladder.
SCOPE_PARAM = {
    'student':       'student_id',
    'class_section': 'class_section_id',
    'highschool':    'highschool_id',
    'term':          'term_id',
    'academic_year': 'academic_year_id',
    'teacher':       'teacher_id',
    'course':        'course_id',
}


# cis detail-page tab `type` -> the column that tab is already scoped by, and
# so should not repeat. A type absent from this map drops nothing.
SCOPE_COLUMN = {
    'student':       'student',
    'course':        'course',
    'class_section': 'class_number',
    'teacher':       'instructor',
    'highschool':    'highschool',
    'term':          'term',
    'academic_year': 'term',
}


_PORTAL_COLUMNS = [
    'submitted_on', 'submitted_by', 'term', 'student', 'course',
    'class_number', 'section_number', 'approvals', 'status', 'edit_action',
]

_CE_COLUMNS = [
    'submitted_on', 'term', 'highschool', 'student', 'course',
    'class_number', 'section_number', 'instructor', 'approvals', 'status',
    'edit_action',
]


# NOTE on `auto_reload_min`: the portal profiles poll every 5 minutes and the
# CE profiles every 10. That asymmetry is inherited from the pre-refactor
# templates (drop_wd/instructor/requests.html used 5, drop_wd/ce/requests_table
# .html used 10) and is deliberate — the CE table is embedded in seven cis
# detail-page tabs and is often left open, so halving its interval would double
# the polling load. Do not "unify" these values.
_PROFILES = {
    'portal': {
        'table_id':      'records_all_drop_requests',
        'columns':       list(_PORTAL_COLUMNS),
        'default_order': [0, 'desc'],   # submitted_on
        'auto_reload_min': 5,
    },
    'portal_approver': {
        'table_id':      'records_all_drop_requests',
        'columns':       ['select'] + list(_PORTAL_COLUMNS),
        # index 1 — the select checkbox column shifts submitted_on right by one
        'default_order': [1, 'desc'],
        'auto_reload_min': 5,
        'bulk_actions':  ['mark_as_approved'],
    },
    # CE index page: standalone, so its detail link opens the iframe modal.
    'ce_index': {
        'table_id':      'records_drop_wd_requests',
        'columns':       list(_CE_COLUMNS),
        'default_order': [0, 'desc'],   # submitted_on
        'auto_reload_min': 10,
        'header_html':   CE_COLUMN_HEADER_HTML,
        'column_set':    'ce',
        'column_search': True,
        'link_style':    'modal',
        'table_global':  'table_drop_wd_requests',
    },
    # The seven cis detail-page tabs. They render inside the record-details
    # iframe, where the modal handler is not available — hence a plain link.
    'ce_record_tab': {
        'table_id':      'records_drop_wd_requests',
        'columns':       list(_CE_COLUMNS),
        'default_order': [0, 'desc'],   # submitted_on
        'auto_reload_min': 10,
        'header_html':   CE_COLUMN_HEADER_HTML,
        'column_set':    'ce',
        'column_search': True,
        'link_style':    'plain',
        'table_global':  'table_drop_wd_requests',
    },
}


def scoped_api_url(base_url, scope_type=None, record_id=None):
    """Append the cis detail-tab scope query param, exactly as before.

    Unknown/absent scope types and a missing record id leave the URL alone.
    """
    param = SCOPE_PARAM.get(scope_type)
    if not param or record_id in (None, ''):
        return base_url
    return '{}&{}={}'.format(base_url, param, record_id)


def build_config(*, variant, api_url, details_prefix='', filter_form_selector=None,
                 scope_type=None):
    """Build the drop_wd requests-table context dict for a call site.

    `scope_type` is the cis detail-page tab type (see SCOPE_COLUMN); the column
    the tab is already scoped by is dropped from the profile's column list.

    KeyError is raised for unknown variants or column keys (fail-fast).
    """
    p = dict(_PROFILES[variant])

    dropped = SCOPE_COLUMN.get(scope_type)
    if dropped and dropped in p['columns']:
        p['columns'] = [c for c in p['columns'] if c != dropped]

    return build_table_config(
        profile=p,
        header_html=p.get('header_html', COLUMN_HEADER_HTML),
        partial_template='drop_wd/_requests_table.html',
        opts={
            'apiUrl':             api_url,
            'columns':            p['columns'],
            'columnSet':          p.get('column_set', 'portal'),
            'columnSearch':       p.get('column_search', False),
            'linkStyle':          p.get('link_style', 'plain'),
            'tableGlobal':        p.get('table_global'),
            'detailsPrefix':      details_prefix,
            'defaultOrder':       p.get('default_order'),
            'autoReloadMinutes':  p.get('auto_reload_min'),
            'bulkActions':        p.get('bulk_actions', []),
            'filterFormSelector': filter_form_selector,
        },
    )
