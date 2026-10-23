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


class InstructorTabTemplateTests(SimpleTestCase):
    def test_feed_url_filters_by_this_section(self):
        # The feed only narrows to the section when the query string reads
        # class_section_id=<id>; '&class_section_id<id>' sends no filter and
        # the tab listed every request the instructor can see.
        from django.template.loader import get_template
        source = get_template(
            'drop_wd/instructor/_class_section_tab.html').template.source
        self.assertIn('&class_section_id={{class_section.id}}', source)
        self.assertNotIn("&class_section_id' +", source)
