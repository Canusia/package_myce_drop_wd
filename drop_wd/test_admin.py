"""drop_wd models are registered in the Django admin and its pages load (#5)."""
from django.contrib import admin
from django.urls import reverse

from .models import DropWDRequest
from .tests import _ScopingFixture


class AdminPagesTests(_ScopingFixture):
    def setUp(self):
        super().setUp()
        from cis.models.customuser import CustomUser
        self.superuser = CustomUser.objects.create_superuser(
            email='admin-dropwd@example.com', username='admin-dropwd@example.com',
            password='pw')
        self.client.force_login(self.superuser)

    def _url(self, name, *args):
        meta = DropWDRequest._meta
        return reverse(f'admin:{meta.app_label}_{meta.model_name}_{name}', args=args)

    def test_every_model_is_registered(self):
        from django.apps import apps
        config = apps.get_containing_app_config(DropWDRequest.__module__)
        for model in config.get_models():
            if model.__name__.startswith('Historical'):
                continue
            with self.subTest(model.__name__):
                self.assertTrue(admin.site.is_registered(model))

    def test_changelist_loads(self):
        response = self.client.get(self._url('changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Scope, Studa')

    def test_changelist_search_and_filters_load(self):
        for params in ({'q': 'Studa'}, {'status__exact': 'requested'},
                       {'registration__class_section__term__id__exact': self.term.id}):
            with self.subTest(params):
                response = self.client.get(self._url('changelist'), params)
                # an unknown lookup would 302 to ?e=1
                self.assertEqual(response.status_code, 200)

    def test_change_and_add_pages_load_with_raw_id_inputs(self):
        response = self.client.get(self._url('change', self.a['request'].pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'vForeignKeyRawIdAdminField')
        self.assertEqual(self.client.get(self._url('add')).status_code, 200)
