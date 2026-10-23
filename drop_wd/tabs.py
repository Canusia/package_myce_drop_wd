"""drop_wd's tab on the instructor portal's class section page.

The instructor portal owns the registry (instructor/registry.py); drop_wd
registers onto it from its own AppConfig.ready(), so the instructor app no
longer needs to know drop_wd exists. On a host without the instructor
portal's registry (an older in-tree instructor app, or none) nothing is
registered and that host keeps whatever it renders itself.
"""
import importlib
import importlib.util

from django.urls import reverse


def _instructor_registry():
    for module in ('instructor.instructor.registry', 'instructor.registry'):
        try:
            if importlib.util.find_spec(module) is not None:
                return importlib.import_module(module)
        except ModuleNotFoundError:  # parent package missing
            continue
    return None


_registry = _instructor_registry()

if _registry is not None:
    from .forms import DropWDRequestForm

    @_registry.instructor_class_section_tabs.tab(
        slug='drop_wd', title='Drop/WD Request(s)', order=30, lazy=False,
        template='drop_wd/instructor/_class_section_tab.html')
    def instructor_class_section_tab(request, class_section):
        return {
            'class_section': class_section,
            'drop_api_url': reverse(
                'instructor_drop_wd:instructor_drop_wd_requests-list')
                + '?format=datatables&portal=instructor',
            'submit_new_drop_request_form': DropWDRequestForm(class_section=class_section),
        }
