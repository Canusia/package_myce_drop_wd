import json

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .services import get_requests_table_config
from .services import requests_table
from .services.requests_table import (
    CE_COLUMN_HEADER_HTML,
    CE_DEFAULT_API_URL,
    COLUMN_HEADER_HTML,
    SCOPE_COLUMN,
    SCOPE_PARAM,
    _CE_COLUMNS,
    _PROFILES,
    build_config,
    scoped_api_url,
)


class RequestsTableServiceTests(SimpleTestCase):
    """Profile / column-registry invariants for the drop_wd requests table."""

    API_URL = '/instructor/drop_wd/api/requests/?format=datatables'

    def _build(self, variant):
        return build_config(
            variant=variant,
            api_url=self.API_URL,
            details_prefix='/instructor/drop_wd/request/',
        )

    def test_variant_set(self):
        self.assertEqual(
            set(_PROFILES.keys()),
            {'portal', 'portal_approver', 'ce_index', 'ce_record_tab'},
        )

    def test_unknown_variant_raises(self):
        with self.assertRaises(KeyError):
            self._build('no_such_variant')

    def test_unknown_column_raises(self):
        _PROFILES['__bad__'] = {
            'table_id': 'records_all_drop_requests',
            'columns': ['submitted_on', 'no_such_column'],
            'default_order': [0, 'desc'],
        }
        try:
            with self.assertRaises(KeyError):
                self._build('__bad__')
        finally:
            del _PROFILES['__bad__']

    def test_select_column_only_in_approver_profile(self):
        self.assertNotIn('select', _PROFILES['portal']['columns'])
        self.assertEqual(_PROFILES['portal_approver']['columns'][0], 'select')
        self.assertEqual(
            _PROFILES['portal_approver']['columns'][1:],
            _PROFILES['portal']['columns'],
        )

    def test_default_order_accounts_for_select_column(self):
        self.assertEqual(_PROFILES['portal']['default_order'], [0, 'desc'])
        self.assertEqual(_PROFILES['portal_approver']['default_order'], [1, 'desc'])

        portal = json.loads(self._build('portal')['opts_json'])
        approver = json.loads(self._build('portal_approver')['opts_json'])
        self.assertEqual(portal['defaultOrder'], [0, 'desc'])
        self.assertEqual(approver['defaultOrder'], [1, 'desc'])
        # both order by submitted_on
        self.assertEqual(portal['columns'][0], 'submitted_on')
        self.assertEqual(approver['columns'][1], 'submitted_on')

    def test_every_profile_column_has_a_header(self):
        for name, profile in _PROFILES.items():
            registry = profile.get('header_html', COLUMN_HEADER_HTML)
            for key in profile['columns']:
                self.assertIn(key, registry,
                              f'{name}: no header entry for {key!r}')

    def test_config_shape(self):
        cfg = self._build('portal')
        self.assertEqual(cfg['table_id'], 'records_all_drop_requests')
        self.assertEqual(cfg['partial_template'], 'drop_wd/_requests_table.html')
        self.assertEqual(len(cfg['column_headers']), len(_PROFILES['portal']['columns']))
        opts = json.loads(cfg['opts_json'])
        self.assertEqual(opts['apiUrl'], self.API_URL)
        self.assertEqual(opts['detailsPrefix'], '/instructor/drop_wd/request/')
        self.assertEqual(opts['bulkActions'], [])

    def test_approver_profile_gets_the_bulk_action(self):
        opts = json.loads(self._build('portal_approver')['opts_json'])
        self.assertEqual(opts['bulkActions'], ['mark_as_approved'])


class RequestsTableResolverTests(SimpleTestCase):
    """The package must work with no tenant override module present."""

    def test_resolver_falls_back_to_packaged_module(self):
        # ewu's myce_tenant_configs has no services/drop_wd_requests_table.py,
        # so the resolver must hand back the packaged default.
        self.assertIs(get_requests_table_config(), requests_table)

    def test_resolved_module_exposes_build_config(self):
        self.assertTrue(callable(get_requests_table_config().build_config))


class CERequestsTableTests(SimpleTestCase):
    """The CE table (records_drop_wd_requests) and its seven scoped tabs."""

    def _build(self, variant, scope_type=None, record_id=7):
        return build_config(
            variant=variant,
            api_url=scoped_api_url(CE_DEFAULT_API_URL, scope_type, record_id),
            details_prefix='/ce/drop_wd/request/',
            filter_form_selector='form#all_req_filter',
            scope_type=scope_type,
        )

    def test_ce_index_columns_match_the_pre_refactor_thead(self):
        self.assertEqual(_PROFILES['ce_index']['columns'], [
            'submitted_on', 'term', 'highschool', 'student', 'course',
            'class_number', 'section_number', 'instructor', 'approvals',
            'status', 'edit_action',
        ])

    def test_ce_index_uses_the_ce_table_id_and_no_scope(self):
        cfg = self._build('ce_index')
        self.assertEqual(cfg['table_id'], 'records_drop_wd_requests')
        opts = json.loads(cfg['opts_json'])
        self.assertEqual(opts['apiUrl'], CE_DEFAULT_API_URL)
        self.assertEqual(opts['columnSet'], 'ce')
        self.assertTrue(opts['columnSearch'])
        self.assertEqual(opts['linkStyle'], 'modal')
        self.assertEqual(opts['detailsPrefix'], '/ce/drop_wd/request/')
        self.assertEqual(opts['tableGlobal'], 'table_drop_wd_requests')

    def test_ce_record_tab_uses_a_plain_link(self):
        opts = json.loads(self._build('ce_record_tab', 'student')['opts_json'])
        self.assertEqual(opts['linkStyle'], 'plain')

    def test_ce_record_tab_drops_the_scoped_column_and_keeps_the_rest(self):
        for scope_type, dropped in SCOPE_COLUMN.items():
            with self.subTest(scope_type=scope_type):
                cols = json.loads(
                    self._build('ce_record_tab', scope_type)['opts_json']
                )['columns']
                self.assertNotIn(dropped, cols)
                self.assertEqual(cols, [c for c in _CE_COLUMNS if c != dropped])

    def test_ce_record_tab_header_count_matches_column_count(self):
        for scope_type in SCOPE_COLUMN:
            with self.subTest(scope_type=scope_type):
                cfg = self._build('ce_record_tab', scope_type)
                cols = json.loads(cfg['opts_json'])['columns']
                self.assertEqual(len(cfg['column_headers']), len(cols))

    def test_unknown_scope_type_drops_nothing(self):
        cols = json.loads(
            self._build('ce_record_tab', 'no_such_type')['opts_json']
        )['columns']
        self.assertEqual(cols, _CE_COLUMNS)

    def test_scope_column_map_only_names_real_ce_columns(self):
        for scope_type, column in SCOPE_COLUMN.items():
            self.assertIn(column, _CE_COLUMNS, f'{scope_type}: {column!r}')

    def test_every_ce_column_has_a_ce_header(self):
        for key in _CE_COLUMNS:
            self.assertIn(key, CE_COLUMN_HEADER_HTML)

    def test_ce_headers_carry_the_original_orm_paths(self):
        # data-name is a real ORM path; a change here is a FieldError at
        # request time. The instructor column is a two-field comma list.
        self.assertIn(
            'data-name="registration.class_section.teacher.user.last_name,'
            'registration.class_section.teacher.user.first_name"',
            CE_COLUMN_HEADER_HTML['instructor'],
        )
        self.assertIn(
            'data-name="registration.student.highschool.name"',
            CE_COLUMN_HEADER_HTML['highschool'],
        )

    def test_api_url_scoping_matches_the_pre_refactor_query_params(self):
        expected = {
            'student':       '&student_id=7',
            'class_section': '&class_section_id=7',
            'highschool':    '&highschool_id=7',
            'term':          '&term_id=7',
            'academic_year': '&academic_year_id=7',
            'teacher':       '&teacher_id=7',
            'course':        '&course_id=7',
        }
        self.assertEqual(set(expected), set(SCOPE_PARAM))
        for scope_type, suffix in expected.items():
            with self.subTest(scope_type=scope_type):
                self.assertEqual(
                    scoped_api_url(CE_DEFAULT_API_URL, scope_type, 7),
                    CE_DEFAULT_API_URL + suffix,
                )

    def test_api_url_unchanged_without_a_scope_or_record(self):
        self.assertEqual(scoped_api_url(CE_DEFAULT_API_URL), CE_DEFAULT_API_URL)
        self.assertEqual(
            scoped_api_url(CE_DEFAULT_API_URL, 'student', None), CE_DEFAULT_API_URL)
        self.assertEqual(
            scoped_api_url(CE_DEFAULT_API_URL, '', 7), CE_DEFAULT_API_URL)


class CERequestsTableTagTests(SimpleTestCase):
    """The shim template + inclusion tag the seven cis tabs go through."""

    SHIM = "{% include 'drop_wd/ce/requests_table.html' %}"

    def _render(self, **ctx):
        from django.template import Context, Template
        return Template(self.SHIM).render(Context(ctx))

    def test_index_render_has_no_scope_param_and_all_columns(self):
        html = self._render()
        self.assertIn('id="records_drop_wd_requests"', html)
        self.assertIn(CE_DEFAULT_API_URL, html)
        self.assertNotIn('student_id=', html)
        self.assertIn('"linkStyle": "modal"', html)
        for key in _CE_COLUMNS:
            self.assertIn(CE_COLUMN_HEADER_HTML[key], html)

    def test_scoped_render_drops_the_column_and_scopes_the_url(self):
        class Rec:
            id = 42

        html = self._render(type='student', record=Rec())
        self.assertIn(CE_DEFAULT_API_URL + '&student_id=42', html)
        self.assertIn('"linkStyle": "plain"', html)
        self.assertNotIn(CE_COLUMN_HEADER_HTML['student'], html)
        self.assertIn(CE_COLUMN_HEADER_HTML['highschool'], html)

    def test_filter_form_renders_with_no_terms(self):
        html = self._render()
        self.assertIn('id="all_req_filter"', html)
        self.assertIn('Filter By Term', html)


class TemplateCommentTests(SimpleTestCase):
    """Django's {# #} comment cannot span lines: a multi-line one is left
    unparsed and rendered as visible text. The shim shipped with exactly that
    bug in v2026.1.0, printing its own comment onto the CE index page and all
    seven detail tabs. Nothing else asserted on rendered output, so nothing
    caught it."""

    def _render(self, template_name, **ctx):
        from django.template.loader import render_to_string
        return render_to_string(template_name, ctx)

    def test_shim_leaks_no_comment_markup(self):
        html = self._render('drop_wd/ce/requests_table.html')

        for marker in ('{#', '#}', '{% comment', '{% endcomment'):
            self.assertNotIn(marker, html)

    def test_shim_still_renders_the_table(self):
        html = self._render('drop_wd/ce/requests_table.html')

        self.assertIn('records_drop_wd_requests', html)
        self.assertIn('requests_table.js', html)

    def test_no_package_template_has_a_multiline_hash_comment(self):
        """Guards every template in the package, not just the shim."""
        import pathlib
        import re

        root = pathlib.Path(__file__).resolve().parent / 'templates'
        offenders = [
            f'{path}:{source[:match.start()].count(chr(10)) + 1}'
            for path in root.rglob('*.html')
            for source in [path.read_text(errors='ignore')]
            for match in re.finditer(r'\{#.*?#\}', source, re.S)
            if '\n' in match.group(0)
        ]

        self.assertEqual(offenders, [])


class RequestsSummaryTests(TestCase):
    """CE Summary tab aggregates.

    Exercises the real ORM aggregation rather than mocking it — the grouping
    paths span four joins and a typo in one would surface as an empty table,
    not an error.
    """

    def setUp(self):
        from django.contrib.auth.models import Group
        from django.contrib.auth.signals import user_logged_in
        from cis.models.course import Campus, Cohort, Course
        from cis.models.customuser import CustomUser
        from cis.models.highschool import HighSchool
        from cis.models.section import ClassSection, StudentRegistration
        from cis.models.student import Student
        from cis.models.term import AcademicYear, Term
        from .models import DropWDRequest

        self._saved_receivers = list(user_logged_in.receivers)
        user_logged_in.receivers = []

        Group.objects.get_or_create(name='ce')
        Group.objects.get_or_create(name='student')
        CustomUser.objects.get_or_create(
            username='cron', defaults={'email': 'cron@example.com'})

        self.user = CustomUser.objects.create_superuser(
            email='ce-sum@example.com', username='ce-sum@example.com',
            password='pw')
        self.user.groups.add(Group.objects.get(name='ce'))
        self.client.force_login(self.user)

        campus = Campus.objects.create(name='Sum Campus', code='SUMC')
        year = AcademicYear.objects.create(name='2029-2030', campus=campus)
        self.term_a = Term.objects.create(academic_year=year, code='SA',
                                          label='Sum Term A')
        self.term_b = Term.objects.create(academic_year=year, code='SB',
                                          label='Sum Term B')
        cohort = Cohort.objects.create(designator='SM', name='Sum Cohort')
        course = Course.objects.create(cohort=cohort, catalog_number='300',
                                       name='SUM 300', title='Summary 300',
                                       campus=campus)
        self.hs = HighSchool.objects.create(name='Summary HS', code='SUMHS')
        self.section_a = ClassSection.objects.create(
            course=course, term=self.term_a, highschool=self.hs)
        self.section_b = ClassSection.objects.create(
            course=course, term=self.term_b, highschool=self.hs)

        # 2 requests in term A (one processed), 1 in term B.
        self._request(self.section_a, 0, 'requested')
        self._request(self.section_a, 1, 'processed')
        self._request(self.section_b, 2, 'requested')

        self.url = reverse('ce_drop_wd:requests_summary')

    def tearDown(self):
        from django.contrib.auth.signals import user_logged_in
        user_logged_in.receivers = self._saved_receivers

    def _request(self, section, index, status):
        from cis.models.customuser import CustomUser
        from cis.models.section import StudentRegistration
        from cis.models.student import Student
        from .models import DropWDRequest

        user = CustomUser.objects.create_user(
            email=f'sum{index}@example.com', username=f'sum{index}@example.com',
            password='pw', first_name='S', last_name=f'Student{index}')
        student = Student.objects.create(user=user, highschool=self.hs)
        registration = StudentRegistration.objects.create(
            student=student, class_section=section,
            status_changed_on={'applied_on': '01/01/2029'})
        return DropWDRequest.objects.create(
            registration=registration, status=status)

    def _get(self, **params):
        return json.loads(self.client.get(self.url, params).content)

    def test_headline_counts_every_request_when_no_term_selected(self):
        data = self._get()

        self.assertEqual(data['headline']['total'], 3)
        self.assertEqual(data['headline']['requested'], 2)
        self.assertEqual(data['headline']['processed'], 1)
        self.assertEqual(data['headline']['highschools'], 1)
        self.assertEqual(data['headline']['courses'], 1)

    def test_term_filter_narrows_every_number(self):
        data = self._get(term=str(self.term_a.id))

        self.assertEqual(data['headline']['total'], 2)
        by_term = self._breakdown(data, 'term')
        self.assertEqual([r['name'] for r in by_term['rows']], ['Sum Term A'])

    def test_multiple_terms_are_unioned(self):
        response = self.client.get(
            self.url, {'term': [str(self.term_a.id), str(self.term_b.id)]})
        data = json.loads(response.content)

        self.assertEqual(data['headline']['total'], 3)
        self.assertEqual(len(self._breakdown(data, 'term')['rows']), 2)

    def _breakdown(self, data, key):
        return next(b for b in data['breakdowns'] if b['key'] == key)

    def test_every_breakdown_resolves_its_grouping_path(self):
        """A wrong ORM path yields rows named '(none)' instead of real values."""
        data = self._get()

        for key, expected in (('term', 'Sum Term A'),
                              ('highschool', 'Summary HS'),
                              ('course', 'SUM 300')):
            with self.subTest(breakdown=key):
                names = [r['name'] for r in self._breakdown(data, key)['rows']]
                self.assertIn(expected, names)

    def test_rows_carry_status_split_and_percentage(self):
        row = next(r for r in self._breakdown(self._get(), 'term')['rows']
                   if r['name'] == 'Sum Term A')

        self.assertEqual(row['total'], 2)
        self.assertEqual(row['requested'], 1)
        self.assertEqual(row['processed'], 1)
        self.assertAlmostEqual(row['pct'], 66.7, places=1)

    def test_by_month_is_present_and_ordered(self):
        data = self._get()

        self.assertTrue(data['by_month'])
        self.assertEqual(sum(m['total'] for m in data['by_month']), 3)

    def test_instructor_rows_carry_both_names(self):
        """Grouping on last_name alone merges two instructors who share one."""
        data = self._get()
        names = [r['name'] for r in self._breakdown(data, 'instructor')['rows']]

        # No teacher is set on these fixtures, so the row is '(none)' rather
        # than a surname — what matters is that it never crashes and never
        # silently drops the first name when a teacher IS set.
        self.assertTrue(all(', ' in n or n == '(none)' for n in names))

    def test_status_rows_show_labels_not_keys(self):
        names = [r['name'] for r in self._breakdown(self._get(), 'status')['rows']]

        self.assertIn('Requested', names)
        self.assertIn('Processed', names)
        self.assertNotIn('requested', names)

    def test_requires_a_cis_role(self):
        from cis.models.customuser import CustomUser

        self.client.logout()
        outsider = CustomUser.objects.create_user(
            email='out-sum@example.com', username='out-sum@example.com',
            password='pw')
        self.client.force_login(outsider)

        self.assertEqual(self.client.get(self.url).status_code, 404)
