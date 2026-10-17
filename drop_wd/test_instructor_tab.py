"""drop_wd registers its own tab on the instructor class section page, so
the instructor portal no longer imports drop_wd to render it."""
import importlib
from unittest import mock

from django.test import SimpleTestCase

from . import tabs


class InstructorTabRegistrationTests(SimpleTestCase):
    def test_registered_on_the_instructor_registry(self):
        registry = tabs._instructor_registry()
        if registry is None:
            self.skipTest('host has no instructor portal registry')
        meta = registry.instructor_class_section_tabs._tabs['drop_wd']
        self.assertEqual(meta['title'], 'Drop/WD Request(s)')
        self.assertEqual(meta['template'], 'drop_wd/instructor/_class_section_tab.html')
        self.assertFalse(meta['lazy'])

    def test_no_registry_registers_nothing(self):
        with mock.patch.object(importlib.util, 'find_spec', return_value=None):
            self.assertIsNone(tabs._instructor_registry())
