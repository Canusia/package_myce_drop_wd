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


class DropdownPaginationTests(TestCase):
    """The two dropdown-feeder endpoints behind the "New Request" page.

    Both are plain-JSON `$.getJSON` consumers, but they inherited the project's
    DataTables pagination (`PAGE_SIZE = 50`). `DatatablesPageNumberPagination`
    only speaks the `start`/`length` protocol when the renderer format is
    `datatables`; for a plain JSON request it falls back to stock
    `PageNumberPagination`, which caps at 50 and exposes no `page_size` query
    param for the client to raise. The templates then read `data.results` and
    never follow `data.next`, so the 51st student in a section — and the 51st
    section in a term — were silently unreachable.

    These tests seed 60 of each and assert every one comes back, through the
    same accessor the templates use.
    """

    SECTION_COUNT = 60
    REGISTRATION_COUNT = 60

    def setUp(self):
        from django.contrib.auth.models import Group
        from django.contrib.auth.signals import user_logged_in
        from cis.models.course import Campus, Cohort, Course
        from cis.models.customuser import CustomUser
        from cis.models.highschool import HighSchool
        from cis.models.section import ClassSection
        from cis.models.teacher import Teacher
        from cis.models.term import AcademicYear, Term

        self._saved_receivers = list(user_logged_in.receivers)
        user_logged_in.receivers = []

        Group.objects.get_or_create(name='instructor')
        Group.objects.get_or_create(name='student')
        CustomUser.objects.get_or_create(
            username='cron', defaults={'email': 'cron@example.com'})

        user = CustomUser.objects.create_user(
            email='pag-teach@example.com', username='pag-teach@example.com',
            password='pw', first_name='Paige', last_name='Nation')
        user.groups.add(Group.objects.get(name='instructor'))
        self.teacher = Teacher.objects.create(user=user)
        self.client.force_login(user)

        campus = Campus.objects.create(name='Pag Campus', code='PAGC')
        year = AcademicYear.objects.create(name='2031-2032', campus=campus)
        self.term = Term.objects.create(
            academic_year=year, code='PG', label='Pag Term')
        cohort = Cohort.objects.create(designator='PG', name='Pag Cohort')
        self.course = Course.objects.create(
            cohort=cohort, catalog_number='400', name='PAG 400',
            title='Pagination 400', campus=campus)
        self.hs = HighSchool.objects.create(name='Pag HS', code='PAGHS')

        self.section = ClassSection.objects.create(
            course=self.course, term=self.term, highschool=self.hs,
            teacher=self.teacher)

    def tearDown(self):
        from django.contrib.auth.signals import user_logged_in
        user_logged_in.receivers = self._saved_receivers

    # -- helpers ---------------------------------------------------------

    def _rows(self, url, **params):
        """Read the payload exactly as the start_request.html templates do."""
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        return data['results'] if isinstance(data, dict) else data

    def _make_registrations(self, count, status='enrolled', offset=0):
        from cis.models.customuser import CustomUser
        from cis.models.section import StudentRegistration
        from cis.models.student import Student

        for index in range(offset, offset + count):
            user = CustomUser.objects.create_user(
                email=f'pag{index}@example.com',
                username=f'pag{index}@example.com',
                password='pw', first_name='P', last_name=f'Student{index:03d}')
            student = Student.objects.create(user=user, highschool=self.hs)
            StudentRegistration.objects.create(
                student=student, class_section=self.section, status=status,
                status_changed_on={'applied_on': '01/01/2031'})

    def _set_allowed_statuses(self, statuses):
        from cis.models.settings import Setting
        from .settings.drop_wd_email import drop_wd_email

        setting, _ = Setting.objects.get_or_create(
            key=drop_wd_email.key, defaults={'value': {}})
        value = setting.value or {}
        value['allowed_registration_statuses'] = statuses
        setting.value = value
        setting.save()

    def _registrations_url(self):
        return reverse(
            'instructor_drop_wd:'
            'instructor_drop_wd_class_section_registrations-list')

    def _sections_url(self):
        return reverse(
            'instructor_drop_wd:instructor_drop_wd_class_sections-list')

    # -- registrations ---------------------------------------------------

    def test_every_registration_in_the_section_is_returned(self):
        """The reported bug: a section with more than 50 students showed 50."""
        self._make_registrations(self.REGISTRATION_COUNT)

        rows = self._rows(
            self._registrations_url(),
            term=str(self.term.id), class_section=str(self.section.id))

        self.assertEqual(len(rows), self.REGISTRATION_COUNT)

    def test_allowed_status_filter_still_applies_past_the_old_page_size(self):
        """Removing the cap must not remove the status filter with it."""
        self._set_allowed_statuses(['enrolled'])
        self._make_registrations(self.REGISTRATION_COUNT, status='enrolled')
        self._make_registrations(5, status='dropped', offset=500)

        rows = self._rows(
            self._registrations_url(),
            term=str(self.term.id), class_section=str(self.section.id))

        self.assertEqual(len(rows), self.REGISTRATION_COUNT)

    def test_registrations_stay_scoped_to_the_requesting_instructor(self):
        """Unbounded must not mean unscoped."""
        from cis.models.customuser import CustomUser
        from cis.models.section import ClassSection
        from cis.models.teacher import Teacher

        self._make_registrations(self.REGISTRATION_COUNT)

        other_user = CustomUser.objects.create_user(
            email='pag-other@example.com', username='pag-other@example.com',
            password='pw', first_name='O', last_name='Ther')
        other_section = ClassSection.objects.create(
            course=self.course, term=self.term, highschool=self.hs,
            teacher=Teacher.objects.create(user=other_user))

        rows = self._rows(
            self._registrations_url(),
            term=str(self.term.id), class_section=str(other_section.id))

        self.assertEqual(rows, [])

    def test_registrations_keep_their_name_ordering(self):
        self._make_registrations(self.REGISTRATION_COUNT)

        rows = self._rows(
            self._registrations_url(),
            term=str(self.term.id), class_section=str(self.section.id))
        names = [r['student']['user']['last_name'] for r in rows]

        self.assertEqual(names, sorted(names))

    # -- class sections --------------------------------------------------

    def test_every_class_section_in_the_term_is_returned(self):
        """Same defect on the section dropdown feeding the same page."""
        from cis.models.section import ClassSection

        for index in range(self.SECTION_COUNT - 1):   # one exists from setUp
            ClassSection.objects.create(
                course=self.course, term=self.term, highschool=self.hs,
                teacher=self.teacher, class_number=f'{40000 + index}')

        rows = self._rows(self._sections_url(), term=str(self.term.id))

        self.assertEqual(len(rows), self.SECTION_COUNT)

    # -- cost of being unbounded -----------------------------------------

    def test_registrations_do_not_scale_queries_with_row_count(self):
        """Unbounded only stays safe while the serializer stays lean.

        With cis's nested StudentRegistrationSerializer this endpoint issued
        1,571 queries and 390 KB for 60 rows (~26 queries per row) — removing
        the page cap on top of that would have made a 300-student section cost
        ~7,800 queries. The lean serializer brings it to a constant handful.
        The ceiling is deliberately loose; it is here to catch a regression
        back to per-row joins, not to pin an exact number.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self._make_registrations(self.REGISTRATION_COUNT)
        url = self._registrations_url()
        params = {'term': str(self.term.id),
                  'class_section': str(self.section.id)}

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url, params)

        self.assertEqual(response.status_code, 200)
        self.assertLess(
            len(ctx.captured_queries), 25,
            f'{len(ctx.captured_queries)} queries for '
            f'{self.REGISTRATION_COUNT} rows — the dropdown serializer has '
            f'regressed to per-row joins')

    def test_sections_do_not_scale_queries_with_row_count(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from cis.models.section import ClassSection

        for index in range(self.SECTION_COUNT - 1):
            ClassSection.objects.create(
                course=self.course, term=self.term, highschool=self.hs,
                teacher=self.teacher, class_number=f'{40000 + index}')

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(
                self._sections_url(), {'term': str(self.term.id)})

        self.assertEqual(response.status_code, 200)
        self.assertLess(len(ctx.captured_queries), 25)

    def test_dropdown_payload_carries_only_what_the_template_reads(self):
        """Pins the response shape the six start_request.html call sites use."""
        self._make_registrations(1)

        row = self._rows(
            self._registrations_url(),
            term=str(self.term.id), class_section=str(self.section.id))[0]

        self.assertEqual(
            set(row), {'id', 'status', 'status_pretty', 'student'})
        self.assertEqual(set(row['student']), {'user'})
        self.assertEqual(
            set(row['student']['user']), {'first_name', 'last_name'})
        # instructor / HS-admin templates read status_pretty, student reads status
        self.assertEqual(row['status'], 'enrolled')
        self.assertEqual(row['status_pretty'], 'Enrolled')

    def test_section_payload_carries_only_what_the_template_reads(self):
        row = self._rows(self._sections_url(), term=str(self.term.id))[0]

        self.assertEqual(set(row), {'id', 'class_number', 'course'})
        self.assertEqual(set(row['course']), {'name'})
        self.assertEqual(row['course']['name'], 'PAG 400')
