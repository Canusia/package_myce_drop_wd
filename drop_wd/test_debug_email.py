"""Debug mode sends Drop/WD emails only to debug_email_list (#15).

Before this, all three send paths replaced the recipients with a hard-coded
personal address whenever Debug was on -- and whenever the server ran with
DEBUG, or had no DEBUG setting at all.
"""
from unittest import mock

from django.http import HttpRequest
from django.test import SimpleTestCase, TestCase, override_settings

from cis.models.settings import Setting

from .services import email as email_service
from .settings import drop_wd_email as settings_module
from .settings.drop_wd_email import SettingForm, drop_wd_email
from .tests import _ScopingFixture


TEMPLATES = {
    'email_to_cep': 'Received {{student_first_name}}',
    'email_subject_to_cep': 'Received',
    'processed_email': 'Processed {{student_first_name}}',
    'processed_email_subject': 'Processed',
}


class ResolveRecipientsTests(SimpleTestCase):
    to = ['student@example.com', 'ce@example.com']

    def test_yes_sends_to_the_real_recipients(self):
        self.assertEqual(
            email_service.resolve_recipients({'is_active': 'Yes'}, self.to), self.to)

    def test_yes_drops_invalid_and_blank_addresses(self):
        self.assertEqual(
            email_service.resolve_recipients(
                {'is_active': 'Yes'}, ['', 'not-an-address', 'ce@example.com']),
            ['ce@example.com'])

    def test_debug_sends_only_to_the_debug_list(self):
        configs = {'is_active': 'Debug',
                   'debug_email_list': 'qa@example.com, lead@example.com'}
        self.assertEqual(
            email_service.resolve_recipients(configs, self.to),
            ['qa@example.com', 'lead@example.com'])

    def test_debug_with_an_empty_list_sends_nothing(self):
        for configs in ({'is_active': 'Debug', 'debug_email_list': ''},
                        {'is_active': 'Debug'}):
            with self.subTest(configs):
                self.assertEqual(
                    email_service.resolve_recipients(configs, self.to), [])

    def test_debug_with_an_empty_list_logs_why_nothing_was_sent(self):
        with self.assertLogs(email_service.logger, level='WARNING'):
            email_service.resolve_recipients({'is_active': 'Debug'}, self.to)

    def test_no_sends_nothing(self):
        self.assertEqual(
            email_service.resolve_recipients(
                {'is_active': 'No', 'debug_email_list': 'qa@example.com'}, self.to),
            [])

    @override_settings(DEBUG=True)
    def test_debug_server_treats_yes_as_debug(self):
        configs = {'is_active': 'Yes', 'debug_email_list': 'qa@example.com'}
        self.assertEqual(
            email_service.resolve_recipients(configs, self.to), ['qa@example.com'])

    @override_settings(DEBUG=True)
    def test_debug_server_with_no_list_sends_nothing(self):
        self.assertEqual(
            email_service.resolve_recipients({'is_active': 'Yes'}, self.to), [])

    def test_send_skips_the_mailer_when_there_is_no_one_to_send_to(self):
        with mock.patch.object(email_service, 'send_html_mail') as send:
            sent = email_service.send_drop_wd_mail(
                {'is_active': 'Debug', 'debug_email_list': ''},
                'Subject', 'text', '<p>html</p>', self.to)
        self.assertEqual(sent, [])
        send.assert_not_called()


class DebugEmailListFormTests(SimpleTestCase):
    def _data(self, **overrides):
        data = {
            'is_active': 'Yes',
            'debug_email_list': '',
            'intro': 'Intro',
            'submit_new_intro': 'Submit intro',
            'processed_email_subject': 'Processed',
            'processed_email': 'Processed',
            'email_address_to_cep': '',
            'email_subject_to_cep': 'Received',
            'email_to_cep': 'Received',
            'form_field_messages': '{}',
        }
        data.update(overrides)
        return data

    def _form(self, **overrides):
        # SettingForm.__init__ reads terms / registration statuses; neither
        # matters here.
        with mock.patch.object(settings_module, 'Term') as term:
            term.objects.all.return_value.order_by.return_value = []
            form = SettingForm(data=self._data(**overrides))
            form.is_valid()
        return form

    def test_debug_with_an_empty_list_is_refused(self):
        form = self._form(is_active='Debug', debug_email_list='')
        self.assertIn('debug_email_list', form.errors)

    def test_debug_with_a_list_saves_it_normalised(self):
        form = self._form(is_active='Debug',
                          debug_email_list='qa@example.com ,lead@example.com')
        self.assertEqual(form.errors, {})
        self.assertEqual(form._to_python()['debug_email_list'],
                         'qa@example.com, lead@example.com')

    def test_invalid_address_is_refused(self):
        form = self._form(is_active='Debug', debug_email_list='qa@example.com, nope')
        self.assertIn('debug_email_list', form.errors)

    def test_yes_needs_no_debug_list(self):
        self.assertEqual(self._form(is_active='Yes').errors, {})


class InstallSeedsNoAddressTests(SimpleTestCase):
    def test_install_defaults_carry_no_email_address(self):
        captured = {}

        def capture(key, defaults):
            captured.update(defaults)

        with mock.patch.object(settings_module, '_install_defaults',
                               side_effect=capture):
            drop_wd_email.install(mock.Mock(key=drop_wd_email.key))

        self.assertEqual(captured['email_address_to_cep'], '')
        self.assertEqual(captured['debug_email_list'], '')
        for key, value in captured.items():
            self.assertNotIn('@', str(value), msg=key)


class SendPathTests(_ScopingFixture):
    """The three real send paths go through the switch."""

    def _configure(self, **values):
        value = dict(TEMPLATES)
        value.update({
            'email_address_to_cep': 'ce-office@example.com',
            'notification_list': ['student', 'instructor', 'highschool_admin'],
        })
        value.update(values)
        Setting.objects.update_or_create(
            key=drop_wd_email.key, defaults={'value': value})

    def _sent_to(self, method):
        request = self.a['request']
        with mock.patch.object(email_service, 'send_html_mail') as send:
            getattr(request, method)()
        return [call.args[4] for call in send.call_args_list]

    def test_debug_routes_every_send_path_to_the_debug_list(self):
        self._configure(is_active='Debug', debug_email_list='qa@example.com')
        for method in ('send_received_notification', 'send_processed_notification'):
            with self.subTest(method):
                sent = self._sent_to(method)
                self.assertTrue(sent)
                for recipients in sent:
                    self.assertEqual(recipients, ['qa@example.com'])

    def test_debug_with_an_empty_list_sends_nothing(self):
        self._configure(is_active='Debug', debug_email_list='')
        for method in ('send_received_notification', 'send_processed_notification'):
            with self.subTest(method):
                self.assertEqual(self._sent_to(method), [])

    @override_settings(DEBUG=True)
    def test_debug_server_never_mails_the_real_recipients(self):
        self._configure(is_active='Yes', debug_email_list='qa@example.com')
        for method in ('send_received_notification', 'send_processed_notification'):
            with self.subTest(method):
                for recipients in self._sent_to(method):
                    self.assertEqual(recipients, ['qa@example.com'])

    def test_yes_mails_the_ce_office(self):
        self._configure(is_active='Yes')
        sent = self._sent_to('send_received_notification')
        self.assertIn(['ce-office@example.com'], sent)

    def test_blank_ce_office_list_does_not_crash_or_send_it(self):
        self._configure(is_active='Yes', email_address_to_cep='')
        sent = self._sent_to('send_received_notification')
        self.assertNotIn([], sent)


class RemoveSeededAddressMigrationTests(TestCase):
    """0006 removes the address every pre-#15 install() seeded as the CE
    office, leaving any address a tenant added itself."""

    def _run(self, stored):
        import importlib
        from django.apps import apps
        migration = importlib.import_module(
            __package__ + '.migrations.0006_remove_seeded_cep_address')
        Setting.objects.filter(key__in=migration.KEYS).delete()
        Setting.objects.create(key=migration.KEYS[0], value={
            'is_active': 'Yes', 'email_address_to_cep': stored})
        migration.remove_seeded_address(apps, None)
        return Setting.objects.get(key=migration.KEYS[0]).value

    def test_seeded_address_removed(self):
        self.assertEqual(self._run('kadaji@gmail.com')['email_address_to_cep'], '')

    def test_tenant_addresses_kept(self):
        value = self._run('ce@school.edu; Kadaji@gmail.com, dean@school.edu')
        self.assertEqual(value['email_address_to_cep'], 'ce@school.edu, dean@school.edu')
        self.assertEqual(value['is_active'], 'Yes')

    def test_untouched_without_it(self):
        self.assertEqual(
            self._run('ce@school.edu;dean@school.edu')['email_address_to_cep'],
            'ce@school.edu;dean@school.edu')
