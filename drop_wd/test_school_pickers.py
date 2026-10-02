"""Campus-scoped school picker on the Drop/WD requests report
(cis HighSchoolCampus)."""
from types import SimpleNamespace

import uuid

from django.conf import settings
from django.test import TestCase, override_settings

from cis.campus_context import campus_context
from cis.models.course import Campus
from cis.models.highschool import HighSchool, HighSchoolCampus


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
