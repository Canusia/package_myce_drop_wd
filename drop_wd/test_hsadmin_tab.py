"""drop_wd's Drop Requests tab on the HS admin class-section page (#16)."""
import importlib
from unittest import mock

from django.test import RequestFactory, SimpleTestCase

from cis.models.settings import Setting

from . import tabs
from .settings.drop_wd_email import drop_wd_email
from .tests import _ScopingFixture


class HSAdminTabTests(_ScopingFixture):
    def setUp(self):
        super().setUp()
        from cis.models.section import StudentRegistration
        from cis.models.student import Student

        # A student from school b in school a's section: same section, but
        # outside the school-a admin's scope.
        other = self._user('studb2', 'student')
        self.outsider = StudentRegistration.objects.create(
            student=Student.objects.create(user=other, highschool=self.b['hs']),
            class_section=self.a['section'], status='enrolled',
            status_changed_on={'applied_on': '01/01/2032'})
        from .models import DropWDRequest
        self.outsider_request = DropWDRequest.objects.create(registration=self.outsider)

    def _settings(self, **value):
        Setting.objects.update_or_create(
            key=drop_wd_email.key, defaults={'value': value})

    def _request(self):
        request = RequestFactory().get('/')
        request.user = self.hsadmin
        return request

    # -- visibility ---------------------------------------------------------

    def test_hidden_when_hs_admins_have_no_part(self):
        for value in ({}, {'start_new_request': ['instructor'],
                           'signatures_required_from': ['student']}):
            with self.subTest(value):
                self._settings(**value)
                self.assertFalse(tabs.hs_admins_use_drop_wd(self.hsadmin, self.a['section']))

    def test_notification_alone_does_not_show_it(self):
        self._settings(notification_list=['highschool_admin'])
        self.assertFalse(tabs.hs_admins_use_drop_wd(self.hsadmin, self.a['section']))

    def test_shown_when_hs_admins_start_or_approve(self):
        for value in ({'start_new_request': ['highschool_admin']},
                      {'signatures_required_from': ['highschool_admin']}):
            with self.subTest(value):
                self._settings(**value)
                self.assertTrue(tabs.hs_admins_use_drop_wd(self.hsadmin, self.a['section']))

    # -- content ------------------------------------------------------------

    def test_lists_only_this_sections_requests_for_the_admins_schools(self):
        self._settings(signatures_required_from=['highschool_admin'])
        ctx = tabs.hsadmin_class_section_requests(self._request(), self.a['section'])
        self.assertEqual(list(ctx['drop_requests']), [self.a['request']])

    def test_other_schools_section_lists_nothing(self):
        self._settings(signatures_required_from=['highschool_admin'])
        ctx = tabs.hsadmin_class_section_requests(self._request(), self.b['section'])
        self.assertEqual(list(ctx['drop_requests']), [])

    def test_start_request_only_when_hs_admins_may_start(self):
        term = str(self.term.id)
        self._settings(signatures_required_from=['highschool_admin'], allowed_terms=[term])
        ctx = tabs.hsadmin_class_section_requests(self._request(), self.a['section'])
        self.assertEqual(ctx['start_request_url'], '')

        self._settings(start_new_request=['highschool_admin'], allowed_terms=[term])
        ctx = tabs.hsadmin_class_section_requests(self._request(), self.a['section'])
        self.assertTrue(ctx['start_request_url'].startswith('/'))

    def test_renders_through_the_registry_with_request_links(self):
        registry = tabs._hsadmin_registry()
        if registry is None:
            self.skipTest('host has no highschool_admin class-section registry')
        self._settings(signatures_required_from=['highschool_admin'])

        rendered = registry.for_record(
            self._request(), self.a['section'], url_for=lambda slug: '')
        self.assertIn('drop_wd', rendered)
        html = rendered['drop_wd']['html']
        from django.urls import reverse
        self.assertIn(reverse('highschool_admin_drop_wd:request',
                              args=[self.a['request'].id]), html)
        self.assertNotIn(str(self.outsider_request.id), html)

    def test_registry_hides_the_tab_per_settings(self):
        registry = tabs._hsadmin_registry()
        if registry is None:
            self.skipTest('host has no highschool_admin class-section registry')
        self._settings()
        rendered = registry.for_record(
            self._request(), self.a['section'], url_for=lambda slug: '')
        self.assertNotIn('drop_wd', rendered)


class HSAdminTabRegistrationTests(SimpleTestCase):
    """Import-time behaviour; no database needed."""

    def test_registered_server_side_with_a_permission(self):
        registry = tabs._hsadmin_registry()
        if registry is None:
            self.skipTest('host has no highschool_admin class-section registry')
        meta = registry._tabs['drop_wd']
        self.assertEqual(meta['title'], 'Drop Requests')
        self.assertFalse(meta['lazy'])
        self.assertIs(meta['permission'], tabs.hs_admins_use_drop_wd)
        self.assertEqual(meta['template'],
                         'drop_wd/highschool_admin/_class_section_requests.html')

    def test_no_highschool_admin_registers_nothing(self):
        with mock.patch.object(importlib.util, 'find_spec', return_value=None):
            self.assertIsNone(tabs._hsadmin_registry())

    def test_missing_parent_package_is_not_an_error(self):
        with mock.patch.object(importlib.util, 'find_spec',
                               side_effect=ModuleNotFoundError('highschool_admin')):
            self.assertIsNone(tabs._hsadmin_registry())

    def test_older_portal_without_the_registry_name_registers_nothing(self):
        fake = mock.Mock(spec=[])  # module present, no hsadmin_class_section_tabs
        with mock.patch.object(importlib.util, 'find_spec', return_value=object()), \
                mock.patch.object(importlib, 'import_module', return_value=fake):
            self.assertIsNone(tabs._hsadmin_registry())
