"""Secondary teachers on a class section (cis#154).

Teacher b is added to section a as a secondary teacher. What b may do there
for Drop/WD follows the DROP_WD capability of the Secondary Teacher Access
setting (default No); the primary teacher is unchanged.
"""
from unittest import mock

from django.urls import reverse

from cis.models.settings import Setting

from . import tabs
from .services import email as email_service
from .settings.drop_wd_email import drop_wd_email
from .tests import _ScopingFixture
from .test_debug_email import TEMPLATES


class _SecondaryFixture(_ScopingFixture):
    def setUp(self):
        super().setUp()
        from cis.models.section_secondary import ClassSectionSecondaryTeacher
        from cis.models.teacher import Teacher
        self.teacher_b = Teacher.objects.get(user=self.b['teacher'])
        ClassSectionSecondaryTeacher.objects.create(
            class_section=self.a['section'], teacher=self.teacher_b)

    def _allow(self, value='Yes'):
        from cis.secondary_access import DROP_WD
        from cis.settings.secondary_teacher_access import secondary_teacher_access
        Setting.objects.update_or_create(
            key=secondary_teacher_access.key,
            defaults={'value': {DROP_WD: value}})


class SecondaryScopeTests(_SecondaryFixture):
    def test_secondary_sees_nothing_extra_by_default(self):
        from .scoping import registrations_for, requests_for
        self.assertEqual(set(registrations_for(self.b['teacher'])),
                         {self.b['registration']})
        self.assertEqual(set(requests_for(self.b['teacher'])), {self.b['request']})

    def test_secondary_sees_the_section_when_allowed(self):
        from .scoping import INSTRUCTOR, registration_in_role_scope, \
            registrations_for, requests_for
        self._allow()
        self.assertEqual(set(registrations_for(self.b['teacher'])),
                         {self.a['registration'], self.b['registration']})
        self.assertEqual(set(requests_for(self.b['teacher'])),
                         {self.a['request'], self.b['request']})
        self.assertTrue(registration_in_role_scope(
            self.b['teacher'], INSTRUCTOR, self.a['registration']))

    def test_primary_unchanged(self):
        from .scoping import registrations_for
        self._allow()
        self.assertEqual(set(registrations_for(self.a['teacher'])),
                         {self.a['registration']})

    def test_hsadmin_at_a_secondary_school_sees_only_own_students(self):
        """HS admin scope is by the student's school, so adding school a as a
        secondary school on section b gives admin a nothing in section b."""
        from cis.models.section_secondary import ClassSectionSecondaryHighSchool
        from .scoping import registrations_for
        ClassSectionSecondaryHighSchool.objects.create(
            class_section=self.b['section'], highschool=self.a['hs'])
        self.assertEqual(set(registrations_for(self.hsadmin)),
                         {self.a['registration']})

    def _section_ids(self, user):
        self.client.force_login(user)
        url = reverse('instructor_drop_wd:instructor_drop_wd_class_sections-list')
        data = self.client.get(url, {'term': str(self.term.id), 'format': 'json'}).json()
        rows = data['results'] if isinstance(data, dict) else data
        return {r['id'] for r in rows}

    def test_section_picker_follows_the_setting(self):
        Setting.objects.update_or_create(
            key=drop_wd_email.key,
            defaults={'value': {'start_new_request': ['instructor']}})
        a, b = str(self.a['section'].id), str(self.b['section'].id)
        self.assertEqual(self._section_ids(self.b['teacher']), {b})
        self._allow()
        self.assertEqual(self._section_ids(self.b['teacher']), {a, b})

    def test_ce_teacher_filter_matches_secondaries(self):
        self.client.force_login(self.ce)
        url = reverse('instructor_drop_wd:instructor_drop_wd_requests-list')
        data = self.client.get(url, {
            'format': 'json', 'teacher_id': str(self.teacher_b.id)}).json()
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual({r['id'] for r in rows},
                         {str(self.a['request'].id), str(self.b['request'].id)})


class SecondaryTabTests(_SecondaryFixture):
    def test_tab_permission(self):
        perm = tabs.instructor_tab_allowed
        section = self.a['section']
        self.assertTrue(perm(self.a['teacher'], section))
        self.assertFalse(perm(self.b['teacher'], section))
        self._allow()
        self.assertTrue(perm(self.b['teacher'], section))
        self.assertFalse(perm(self.hsadmin, section))

    def test_tab_registered_with_the_permission(self):
        registry = tabs._instructor_registry()
        if registry is None:
            self.skipTest('host has no instructor portal registry')
        meta = registry.instructor_class_section_tabs._tabs['drop_wd']
        self.assertIs(meta['permission'], tabs.instructor_tab_allowed)


class SecondaryEmailTests(_SecondaryFixture):
    def setUp(self):
        super().setUp()
        value = dict(TEMPLATES)
        value.update({
            'is_active': 'Yes',
            'email_address_to_cep': 'ce-office@example.com',
            'notification_list': ['instructor'],
        })
        Setting.objects.update_or_create(
            key=drop_wd_email.key, defaults={'value': value})

    def _recipients(self, method):
        with mock.patch.object(email_service, 'send_html_mail') as send:
            getattr(self.a['request'], method)()
        return {addr for call in send.call_args_list for addr in call.args[4]}

    def test_secondary_not_mailed_by_default(self):
        for method in ('send_received_notification', 'send_processed_notification'):
            with self.subTest(method):
                sent = self._recipients(method)
                self.assertIn(self.a['teacher'].email, sent)
                self.assertNotIn(self.b['teacher'].email, sent)

    def test_secondary_mailed_when_allowed(self):
        self._allow()
        for method in ('send_received_notification', 'send_processed_notification'):
            with self.subTest(method):
                sent = self._recipients(method)
                self.assertIn(self.a['teacher'].email, sent)
                self.assertIn(self.b['teacher'].email, sent)


class OlderCisFallbackTests(_SecondaryFixture):
    """On a cis without secondary_access only the primary counts."""

    def test_primary_only_without_secondary_access(self):
        from . import secondary
        from .scoping import registrations_for
        self._allow()
        with mock.patch.object(secondary, '_has_module', return_value=False):
            self.assertEqual(set(registrations_for(self.b['teacher'])),
                             {self.b['registration']})
            self.assertFalse(secondary.user_can(self.a['section'], self.b['teacher']))
            self.assertTrue(secondary.user_can(self.a['section'], self.a['teacher']))
            self.assertEqual(secondary.notified_users(self.a['section']),
                             [self.a['teacher']])
