"""#142: drop / withdraw deadlines come from the registration's term.

A request is a drop until the term's drop deadline and a withdrawal after it,
until the withdraw deadline. Past the deadline that applies, student / HS (and
instructor) requests are refused; CE administrators never are. Blank = no limit.
"""
import datetime
from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from .models import DropWDRequest
from .tests import _ScopingFixture


def _d(m, d):
    return datetime.date(2032, m, d)


class DeadlineRefusalTests(SimpleTestCase):
    """DropWDRequest.deadline_refusal on a stand-in term."""

    def _term(self, drop=None, withdraw=None, label='Fall 2032'):
        dates = {'drop_deadline_on': drop, 'withdraw_deadline_on': withdraw}
        term = mock.MagicMock()
        term.operational_date.side_effect = lambda name: dates[name]
        term.__str__.return_value = label
        return term

    def refusal(self, term, today):
        return DropWDRequest.deadline_refusal(term, today)

    def test_blank_is_no_limit(self):
        self.assertIsNone(self.refusal(self._term(), _d(12, 31)))

    def test_drop_deadline_day_allowed_after_refused(self):
        term = self._term(drop=_d(9, 15))
        self.assertIsNone(self.refusal(term, _d(9, 15)))
        self.assertEqual(self.refusal(term, _d(9, 16)),
                         'The drop deadline for Fall 2032 was 09/15/2032.')

    def test_withdraw_deadline_day_allowed_after_refused(self):
        term = self._term(withdraw=_d(11, 1))
        self.assertIsNone(self.refusal(term, _d(11, 1)))
        self.assertEqual(self.refusal(term, _d(11, 2)),
                         'The withdraw deadline for Fall 2032 was 11/01/2032.')

    def test_only_the_later_deadline_ends_requests(self):
        # Drop and withdraw are one kind of request here: a drop until the
        # drop deadline, a withdrawal until the withdraw deadline. Past both,
        # nothing is accepted; the message names the one that ended last.
        term = self._term(drop=_d(9, 15), withdraw=_d(11, 1))
        self.assertIsNone(self.refusal(term, _d(9, 16)))

    def test_between_the_two_is_a_withdrawal(self):
        term = self._term(drop=_d(9, 15), withdraw=_d(11, 1))
        self.assertIsNone(self.refusal(term, _d(10, 1)))
        self.assertEqual(self.refusal(term, _d(11, 2)),
                         'The withdraw deadline for Fall 2032 was 11/01/2032.')

    def test_older_cis_without_operational_date_is_unchanged(self):
        self.assertIsNone(self.refusal(object(), _d(12, 31)))
        self.assertIsNone(self.refusal(None, _d(12, 31)))


class DeadlineSubmitTests(_ScopingFixture):
    def _set_dates(self, **dates):
        from cis.models.term import Term
        Term.objects.filter(pk=self.term.pk).update(**dates)

    def _allow(self, *roles):
        from cis.models.settings import Setting
        from .settings.drop_wd_email import drop_wd_email
        setting, _ = Setting.objects.get_or_create(
            key=drop_wd_email.key, defaults={'value': {}})
        setting.value = {**setting.value, 'start_new_request': list(roles)}
        setting.save()

    def _submit(self, user, side, today, ns='instructor_drop_wd'):
        registration = side['registration']
        DropWDRequest.objects.filter(registration=registration).delete()
        self.client.force_login(user)
        with mock.patch('django.utils.timezone.localdate', return_value=today):
            return self.client.post(reverse(f'{ns}:submit_request'), {
                'term': str(self.term.id),
                'class_section': str(registration.class_section.id),
                'registration': str(registration.id),
                'note': 'please drop',
            })

    def test_hs_admin_refused_after_deadline_allowed_on_it(self):
        self._allow('highschool_admin')
        self._set_dates(drop_deadline_on=_d(9, 15))
        late = self._submit(self.hsadmin, self.a, _d(9, 16))
        self.assertEqual(late.status_code, 400, late.content)
        self.assertIn('The drop deadline for', late.json()['errors'])
        self.assertFalse(DropWDRequest.objects.filter(
            registration=self.a['registration']).exists())
        on_day = self._submit(self.hsadmin, self.a, _d(9, 15))
        self.assertEqual(on_day.status_code, 200, on_day.content)

    def test_student_refused_after_deadline(self):
        self._allow('student')
        self._set_dates(drop_deadline_on=_d(9, 15), withdraw_deadline_on=_d(11, 1))
        ok = self._submit(self.a['student'], self.a, _d(10, 1))
        self.assertEqual(ok.status_code, 200, ok.content)
        late = self._submit(self.a['student'], self.a, _d(11, 2))
        self.assertEqual(late.status_code, 400, late.content)
        self.assertIn('The withdraw deadline for', late.json()['errors'])

    def test_ce_is_never_blocked(self):
        self._set_dates(drop_deadline_on=_d(9, 15), withdraw_deadline_on=_d(11, 1))
        response = self._submit(self.ce, self.a, _d(12, 31))
        self.assertEqual(response.status_code, 200, response.content)

    def test_blank_dates_are_no_limit(self):
        self._allow('highschool_admin')
        response = self._submit(self.hsadmin, self.a, _d(12, 31))
        self.assertEqual(response.status_code, 200, response.content)
