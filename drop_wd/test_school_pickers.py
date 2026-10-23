"""Campus-scoped school picker on the Drop/WD requests report
(cis HighSchoolCampus).

The campus picker needs cis.highschool_scope, which only the packaged
multi-campus cis (the optional `campus` extra) ships. On a tenant that keeps
cis in its own repo these tests skip; FallbackPickerTests covers that path.
"""
import importlib
import importlib.util
from types import SimpleNamespace
from unittest import mock, skipUnless

import uuid

from django.conf import settings
from django.test import TestCase, override_settings

from cis.models.course import Campus
from cis.models.highschool import HighSchool

HAS_CAMPUS_SCOPE = importlib.util.find_spec('cis.highschool_scope') is not None

if HAS_CAMPUS_SCOPE:
    from cis.campus_context import campus_context
    from cis.models.highschool import HighSchoolCampus


def _sfx():
    return uuid.uuid4().hex[:8]


def _campus():
    return Campus.objects.create(
        name=f"C-{_sfx()}", code=f"{settings.CAMPUS_CODE_PREFIX}_{_sfx()[:6]}")


def _hs(name, campus=None, status="Active"):
    hs = HighSchool.objects.create(name=name, code=_sfx())
    HighSchoolCampus.objects.filter(highschool=hs).delete()
    if campus is not None:
        HighSchoolCampus.objects.create(
            highschool=hs, campus=campus, status=status)
    return hs


@skipUnless(HAS_CAMPUS_SCOPE, 'cis has no highschool_scope (in-repo cis)')
class _Base(TestCase):
    def setUp(self):
        self.a, self.b = _campus(), _campus()
        self.mine = _hs("Mine", self.a)
        self.foreign = _hs("Foreign", self.b)
        self.dormant = _hs("Dormant", self.a, "Inactive")


from .reports.drop_wd_requests import drop_wd_requests


class _User:
    def get_roles(self):
        return ['ce']


def _names():
    request = SimpleNamespace(user=_User(), GET={'report_id': '1'})
    return list(drop_wd_requests(request).fields['highschools']
                .queryset.values_list('name', flat=True))


@override_settings(MULTI_CAMPUS=True)
class MultiCampusTests(_Base):
    def test_excludes_other_campus_and_inactive_schools(self):
        with campus_context(self.a):
            self.assertEqual(_names(), ['Mine'])

    def test_follows_the_request_campus(self):
        with campus_context(self.b):
            self.assertEqual(_names(), ['Foreign'])


@override_settings(MULTI_CAMPUS=False)
class SingleCampusTests(_Base):
    def test_options_are_campus_linked_active_schools(self):
        with campus_context(self.a):
            self.assertEqual(_names(), ['Mine'])


class FallbackPickerTests(TestCase):
    """Without cis.highschool_scope the report falls back to the
    pre-v2026.2.5 picker: active schools, by name (#17)."""

    def test_fallback_lists_active_schools_by_name(self):
        from .reports import drop_wd_requests as report_module

        HighSchool.objects.create(name='Zeta Fallback', code=_sfx())
        HighSchool.objects.create(name='Alpha Fallback', code=_sfx())
        HighSchool.objects.create(
            name='Dormant Fallback', code=_sfx(), status='Inactive')

        real_find_spec = importlib.util.find_spec

        def no_scope(name, *args, **kwargs):
            if name == 'cis.highschool_scope':
                return None
            return real_find_spec(name, *args, **kwargs)

        try:
            with mock.patch.object(importlib.util, 'find_spec', no_scope):
                importlib.reload(report_module)
            names = [n for n in report_module.picker_queryset()
                     .values_list('name', flat=True) if 'Fallback' in n]
            self.assertEqual(names, ['Alpha Fallback', 'Zeta Fallback'])
        finally:
            importlib.reload(report_module)
