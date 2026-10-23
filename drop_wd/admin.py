"""Django admin for drop_wd (#5), with change history (#4).

Foreign keys are raw-id inputs: a select over every user or student
registration would render tens of thousands of options. (autocomplete_fields
would need search_fields on cis's admins, which not every tenant's cis has.)
"""
from django.apps import apps
from django.contrib import admin

from .models import DropWDRequest

# The History button needs simple_history's admin templates, which load only
# when the tenant lists 'simple_history' in INSTALLED_APPS. Several tenants
# have the package (DropWDRequest.history needs only that) but not the app,
# so fall back to the plain admin there rather than 500 on the history page.
if apps.is_installed('simple_history'):
    from simple_history.admin import SimpleHistoryAdmin as _BaseAdmin
else:
    _BaseAdmin = admin.ModelAdmin


@admin.register(DropWDRequest)
class DropWDRequestAdmin(_BaseAdmin):
    list_display = (
        'created_on', 'student', 'course', 'class_number', 'term', 'status',
        'student_signature', 'parent_signature', 'instructor_signature',
        'counselor_signature',
    )
    list_filter = (
        'status', 'created_on',
        'student_signature', 'parent_signature', 'instructor_signature',
        'counselor_signature',
        ('registration__class_section__term', admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        'id',
        'registration__student__user__first_name',
        'registration__student__user__last_name',
        'registration__student__user__email',
        'registration__class_section__course__name',
        'registration__class_section__class_number',
        'created_by__email',
    )
    raw_id_fields = ('registration', 'created_by', 'processed_by')
    readonly_fields = ('id', 'created_on')
    date_hierarchy = 'created_on'
    ordering = ('-created_on',)
    list_select_related = (
        'registration__student__user',
        'registration__class_section__course',
        'registration__class_section__term',
    )

    @admin.display(description='Student',
                   ordering='registration__student__user__last_name')
    def student(self, obj):
        user = obj.registration.student.user
        return f'{user.last_name}, {user.first_name}'

    @admin.display(description='Course',
                   ordering='registration__class_section__course__name')
    def course(self, obj):
        return obj.registration.class_section.course.name

    @admin.display(description='Section',
                   ordering='registration__class_section__class_number')
    def class_number(self, obj):
        return obj.registration.class_section.class_number

    @admin.display(description='Term',
                   ordering='registration__class_section__term__code')
    def term(self, obj):
        return obj.registration.class_section.term
