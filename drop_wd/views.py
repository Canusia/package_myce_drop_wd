import logging

from django.contrib import messages
from django.http import JsonResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.views.decorators.clickjacking import xframe_options_exempt

from rest_framework import viewsets
from django.urls import reverse
from django.core.mail import send_mail
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from cis.serializers.class_section import ClassSectionSerializer
from cis.serializers.registration import StudentRegistrationSerializer

from cis.models.term import Term
from .settings.drop_wd_email import drop_wd_email as drop_wd_settings 
from django.shortcuts import render
from django.db.models import Count

from django.core.exceptions import FieldError
from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, F, Value
from django.db.models.functions import Coalesce, Concat

from cis.utils import (
    user_has_instructor_role,
    user_has_highschool_admin_role,
    user_has_student_role,
    user_has_cis_role,
    INSTRUCTOR_user_only,
    CIS_user_only,
    HSADMIN_user_only,
    STUDENT_user_only
)
from cis.models.section import ClassSection, StudentRegistration
from cis.models.highschool_administrator import HSAdministrator

from cis.menu import (
    INSTRUCTOR_MENU,
    HS_ADMIN_MENU,
    STUDENT_MENU,
    cis_menu,
    draw_menu
)
from cis.forms.section import EditStudentRegistration
from .forms import drop_wd_email


from .models import DropWDRequest
from .forms import DropWDRequestForm, DropWDSignatureForm, EditDropWDRequestForm, StudentDropWDRequestForm, RequestReviewForm
from .serializers import (
    DropWDRequestSerializer,
    DropWDMetricsSerializer,
    GroupCountSerializer,
)


logger = logging.getLogger(__name__)

class ClassRegistrationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentRegistrationSerializer
    permission_classes = [INSTRUCTOR_user_only|CIS_user_only|HSADMIN_user_only|STUDENT_user_only]

    def get_queryset(self):
        class_section = self.request.GET.get('class_section', '').strip()
        term = self.request.GET.get('term', '').strip()

        user = self.request.user

        try:
            records = StudentRegistration.objects.filter(
                class_section__term__id=term,
                class_section__id=class_section
            ).exclude(
                id__in=DropWDRequest.objects.filter(registration__class_section__id=class_section).values_list('registration_id', flat=True)
            )

            if user_has_cis_role(user):
                pass
            elif user_has_student_role(user):
                records = records.filter(
                    student__user=user
                )
            elif user_has_instructor_role(user):
                records = records.filter(
                    class_section__teacher__user=user
                )
            elif user_has_highschool_admin_role(user):
                user = HSAdministrator.objects.get(user__id=user.id)
                highschools = user.get_highschools()

                records = records.filter(
                    student__highschool__id__in=highschools.values_list('id', flat=True)
                )
            
            records = records.order_by(
                'student__user__last_name', 'student__user__first_name'
            )
        except:
            return StudentRegistration.objects.none()

        return records

class ClassSectionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ClassSectionSerializer
    permission_classes = [INSTRUCTOR_user_only|CIS_user_only|HSADMIN_user_only|STUDENT_user_only]


    def get_queryset(self):
        term = self.request.GET.get('term', '').strip()
        user = self.request.user

        try:
            records = ClassSection.objects.filter(
                term__id=term
            )
            if user_has_instructor_role(user):
                records = records.filter(
                    teacher__user=user
                )
            elif user_has_highschool_admin_role(user):
                user = HSAdministrator.objects.get(user__id=user.id)
                highschools = user.get_highschools()

                records = records.filter(
                    highschool__id__in=highschools.values_list('id', flat=True)
                )
            elif user_has_student_role(user):
                records = records.filter(
                    id__in=StudentRegistration.objects.filter(
                        student__user=user
                    ).values_list('class_section__id')
                )
            
            records = records.order_by(
                'course__name'
            )
        except Exception as e:
            print(e)
            return ClassSection.objects.none()

        return records

class DropWDRequestViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DropWDRequestSerializer
    permission_classes = [INSTRUCTOR_user_only|CIS_user_only|HSADMIN_user_only|STUDENT_user_only]

    # ------- helpers -------
    def _counts_by_status(self, qs):
        rows = (
            qs.values("status")
              .annotate(count=Count("id"))
              .order_by("-count", "status")
        )
        return [{"key": r["status"], "label": r["status"], "count": r["count"]} for r in rows]

    def _try_group(self, qs, key_field, label_field_candidates):
        """
        Attempt to group by `key_field` and one of `label_field_candidates` if present.
        Falls back to key-only grouping when label fields don't exist.
        Returns a list of {key, label, count}.
        """
        # Try each label field until one works
        for label_field in label_field_candidates:
            try:
                rows = (
                    qs.values(key_field, label_field)
                      .annotate(count=Count("id"))
                      .order_by("-count", key_field)
                )
                # If we got here, the label_field exists
                out = []
                for r in rows:
                    out.append({
                        "key": r.get(key_field),
                        "label": r.get(label_field),
                        "count": r["count"],
                    })
                return out
            except FieldError:
                continue

        # Fallback: no label field—group by key only
        rows = (
            qs.values(key_field)
              .annotate(count=Count("id"))
              .order_by("-count", key_field)
        )
        return [{"key": r.get(key_field), "label": None, "count": r["count"]} for r in rows]

    def _counts_by_teacher(self, qs):
        # Teacher lives at registration -> class_section -> teacher
        key = "registration__class_section__teacher_id"

        # First, try common single-field labels via _try_group
        label_candidates = [
            "registration__class_section__teacher__user__last_name",
            "registration__class_section__teacher__user__first_name",
            # "registration__class_section__teacher__user__name",
            "registration__class_section__teacher__user__email",
        ]
        out = self._try_group(qs, key, label_candidates)
        if any(item.get("label") for item in out):
            return out

        # Fallback: build "First Last" via Concat; allows null-safe labeling
        rows = (
            qs.annotate(
                _t_id=F("registration__class_section__teacher_id"),
                _t_label=Concat(
                    Coalesce(F("registration__class_section__teacher__user__first_name"), Value("")),
                    Value(" "),
                    Coalesce(F("registration__class_section__teacher__user__last_name"), Value("")),
                ),
            )
            .values("_t_id", "_t_label")
            .annotate(count=Count("id"))
            .order_by("-count", "_t_label")
        )
        return [
            {"key": r["_t_id"], "label": (r["_t_label"].strip() or None), "count": r["count"]}
            for r in rows
        ]
    
    def _counts_by_course(self, qs):
        # Course lives at registration -> class_section -> course
        key = "registration__class_section__course_id"
        label_candidates = [
            "registration__class_section__course__title",
            "registration__class_section__course__name",
            "registration__class_section__course__course_title",
            "registration__class_section__course__course_name",
            "registration__class_section__course__code",
            "registration__class_section__course__number",
        ]
        return self._try_group(qs, key, label_candidates)

    def _counts_by_highschool(self, qs):
        # HighSchool lives at registration -> class_section -> highschool
        key = "registration__class_section__highschool_id"
        label_candidates = [
            "registration__class_section__highschool__name",
            "registration__class_section__highschool__title"
        ]
        return self._try_group(qs, key, label_candidates)

    def _counts_by_pending_signatures(self, qs):
        """Calculate pending signature counts based on configuration"""
        from .settings.drop_wd_email import drop_wd_email as drop_wd_settings
        configs = drop_wd_settings.from_db()
        
        pending_signatures = {}
        
        if 'student' in configs.get('signatures_required_from', []):
            pending_signatures['student'] = qs.filter(
                student_signature='Pending'
            ).count()
        
        if 'parent' in configs.get('signatures_required_from', []):
            pending_signatures['parent'] = qs.filter(
                parent_signature='Pending'
            ).count()
        
        if 'instructor' in configs.get('signatures_required_from', []):
            pending_signatures['instructor'] = qs.filter(
                instructor_signature='Pending'
            ).count()

        if 'highschool_admin' in configs.get('signatures_required_from', []):
            pending_signatures['counselor'] = qs.filter(
                counselor_signature='Pending'
            ).count()
        
        return pending_signatures

    # ------- combined metrics -------
    @action(detail=False, methods=["get"], url_path="metrics")
    def metrics(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        
        payload = {
            "by_status": self._counts_by_status(qs),
            "by_course": self._counts_by_course(qs),
            "by_highschool": self._counts_by_highschool(qs),
            "pending_signatures": self._counts_by_pending_signatures(qs),
        }
        return Response(DropWDMetricsSerializer(payload).data)

    @action(detail=False, methods=["get"], url_path="by-teacher")
    def by_teacher(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        data = self._counts_by_teacher(qs)
        return Response(GroupCountSerializer(data, many=True).data)
    
    # ------- individual endpoints (optional convenience) -------
    @action(detail=False, methods=["get"], url_path="by-status")
    def by_status(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        data = self._counts_by_status(qs)
        return Response(GroupCountSerializer(data, many=True).data)

    @action(detail=False, methods=["get"], url_path="by-course")
    def by_course(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        data = self._counts_by_course(qs)
        return Response(GroupCountSerializer(data, many=True).data)

    @action(detail=False, methods=["get"], url_path="by-highschool")
    def by_highschool(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        data = self._counts_by_highschool(qs)
        return Response(GroupCountSerializer(data, many=True).data)
    
    def get_queryset(self):
        user = self.request.user
        term = self.request.GET.get('term', '').strip()
        term_id = self.request.GET.get('term_id', '').strip()
        class_section_id = self.request.GET.get('class_section_id', '').strip()
        student_id = self.request.GET.get('student_id', '').strip()
        highschool_id = self.request.GET.get('highschool_id', '').strip()
        academic_year_id = self.request.GET.get('academic_year_id', '').strip()
        teacher_id = self.request.GET.get('teacher_id', '').strip()
        course_id = self.request.GET.get('course_id', '').strip()

        if user_has_instructor_role(user):
            records = DropWDRequest.objects.filter(
                registration__class_section__teacher__user=user
            )
        elif user_has_student_role(user):
            records = DropWDRequest.objects.filter(
                registration__student__user=user
            )
        
        if user_has_highschool_admin_role(user):
            try:
                hsadmin = HSAdministrator.objects.get(user__id=user.id)
                highschools = hsadmin.get_highschools()

                records = DropWDRequest.objects.filter(
                    registration__student__highschool__id__in=highschools.values_list('id', flat=True)
                )
            except:
                ...
        
        if user_has_cis_role(user):
            records = DropWDRequest.objects.all()

        try:
            if student_id:
                records = records.filter(
                    registration__student__id=student_id
                )

            if highschool_id:
                records = records.filter(
                    registration__student__highschool__id=highschool_id
                )

            if academic_year_id:
                records = records.filter(
                    registration__class_section__term__academic_year__id=academic_year_id
                )

            if teacher_id:
                records = records.filter(
                    registration__class_section__teacher__id=teacher_id
                )
            
            if course_id:
                records = records.filter(
                    registration__class_section__course__id=course_id
                )

            if term:
                records = records.filter(
                    registration__class_section__term__id=term
                )

            if term_id:
                records = records.filter(
                    registration__class_section__term__id=term_id
                )

            if class_section_id:
                records = records.filter(
                    registration__class_section__id=class_section_id
                )
        except Exception as e:
            logger.error(e)

        return records

def submit_request(request):
    """
    Called when a new request is started. Could be initiated by teacher, counselor, or student
    """
    template_name = 'drop_wd/instructor/start_request.html'
    
    if request.method == 'POST':
        if user_has_student_role(request.user):
            form = StudentDropWDRequestForm(student=request.user.student, data=request.POST)
        else:
            form = DropWDRequestForm(data=request.POST)

        if form.is_valid():
            try:
                drop_req = form.save(request)
                return JsonResponse({
                    'message': 'Successfully submitted your request',
                    'status': 'success'
                }, status=200)
            except Exception as e:
                logger.error(e)
                return JsonResponse({
                    'title': 'Unable to complete request',
                    'message': 'There was an error processing your request.',
                    'status': 'error'
                }, status=400)
        else:
            return JsonResponse({
                'title': 'Unable to complete request',
                'message': 'Please correct the errors and try again',
                'errors': form.errors.as_json()
            }, status=400)
    else:
        if user_has_student_role(request.user):
            form = StudentDropWDRequestForm(student=request.user.student)
        else:
            form = DropWDRequestForm()
 
    return render(
        request,
        template_name,
        {
            'form': form
        }
    )

@login_required
@require_POST 
def do_bulk_action(request):
    action = request.POST.get('action')
    ids = request.POST.getlist('ids[]')
    
    if not ids:
        return JsonResponse({'message': 'No records were selected.', 'status': 'error'}, status=400)

    if action == 'mark_as_approved':
        if not ids:
            return JsonResponse({'message': 'No records were selected.', 'status': 'error'}, status=400)
        
        if user_has_instructor_role(request.user):
            reqs = DropWDRequest.objects.filter(id__in=ids)
            reqs.update(instructor_signature='Approved')
            return JsonResponse({'message': 'Successfully marked as approved', 'status': 'success'})
        
        elif user_has_highschool_admin_role(request.user):
            reqs = DropWDRequest.objects.filter(id__in=ids)
            reqs.update(counselor_signature='Approved')
            return JsonResponse({'message': 'Successfully marked as approved', 'status': 'success'})
        
        elif user_has_student_role(request.user):
            reqs = DropWDRequest.objects.filter(id__in=ids)
            reqs.update(student_signature='Approved')
            return JsonResponse({'message': 'Successfully marked as approved', 'status': 'success'})
        
        return JsonResponse({'message': 'You do not have permission to perform this action.', 'status': 'error'}, status=403)

    elif action == 'delete_requests':
        if not user_has_highschool_admin_role(request.user) and not request.user.is_staff:
            return JsonResponse({'message': 'You do not have permission to perform this action.', 'status': 'error'}, status=403)
        
        try:
            requests_to_delete = DropWDRequest.objects.filter(id__in=ids)
            deleted_count, _ = requests_to_delete.delete()
            return JsonResponse({'message': f'Successfully deleted {deleted_count} request(s).', 'status': 'success'})
        except Exception as e:
            return JsonResponse({'message': f'An error occurred: {str(e)}', 'status': 'error'}, status=500)

    return JsonResponse({'message': 'Invalid action specified.', 'status': 'error'}, status=400)

@xframe_options_exempt
def drop_request(request, record_id):

    record = get_object_or_404(DropWDRequest, pk=record_id)
    needs_to_approve = False

    if user_has_cis_role(request.user):
        template = 'drop_wd/ce/request.html'
        
    elif user_has_instructor_role(request.user):
        template = 'drop_wd/instructor/request.html'
        if record.registration.class_section.teacher.user != request.user:
            raise Http404

        needs_to_approve = record.record_needs_instructor_approval()

    elif user_has_highschool_admin_role(request.user):
        template = 'drop_wd/highschool_admin/request.html'
        user = HSAdministrator.objects.get(user__id=request.user.id)
        highschools = user.get_highschools()

        if record.registration.student.highschool.id in highschools:
            raise Http404

        needs_to_approve = record.record_needs_student_approval()

    elif user_has_student_role(request.user):
        template = 'drop_wd/student/request.html'
        if record.registration.student.user != request.user:
            raise Http404

        needs_to_approve = record.record_needs_student_approval()

    edit_request_form = EditDropWDRequestForm(
        record
    )

    review_req_form = RequestReviewForm()

    if request.method == 'POST':
        if request.POST.get('action') == 'review_request':
            review_req_form = RequestReviewForm(request.POST)
            if review_req_form.is_valid():
                record = review_req_form.save(request, record)
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Successfully saved your decision.',
                    'list-group-item-success'
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Please fix the error(s) and try again.',
                    'list-group-item-danger'
                )
        elif request.POST.get('action') == 'update_drop_wd_request':
            edit_request_form = EditDropWDRequestForm(record, request.POST)
            if edit_request_form.is_valid():
                edit_request_form.save(request, record)
                
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Successfully updated request.',
                    'list-group-item-success'
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Please fix the error(s) and try again.',
                    'list-group-item-danger'
                )
        else:
            form = DropWDSignatureForm(request.POST)

            if form.is_valid():
                signature = form.save(request, record)
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Successfully saved signature.',
                    'list-group-item-success'
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Please fix the error(s) and try again.',
                    'list-group-item-danger'
                )


    return render(
        request,
        template, {
            'student_form': DropWDSignatureForm(
                initial={
                    'id':record.id,
                    'signature_type': 'student'
                }),
            'parent_form': DropWDSignatureForm(
                initial={
                    'id':record.id,
                    'signature_type': 'parent'
                }),
            'review_request_form': review_req_form,
            'needs_to_approve': needs_to_approve,
            'record': record,
            'edit_request_form': edit_request_form,
            'student': record.registration.student,
            'registration': record.registration
        })

def delete_record(request, record_id):
    record = get_object_or_404(DropWDRequest, pk=record_id)
    
    try:
        record.delete()

        data = {
            'status':'success',
            'message':'Successfully deleted record',
            'action': 'reload'
        }
    except Exception as e:
        data = {
            'status':'error',
            'message':'Unable to delete record. ' + str(e),
            'action': ''
        }
    return JsonResponse(data)

def requests(request):
    '''
     search and index page for requests
    '''
    menu = {}
    intro = ''

    from .settings.drop_wd_email import drop_wd_email as drop_wd_settings

    page_settings = drop_wd_settings.from_db()

    can_submit_new_request = needs_to_approve = False
    url_prefix = ''
    if user_has_cis_role(request.user):
        menu = draw_menu(cis_menu, 'students', 'drop_wd_requests', 'ce')
        template = 'drop_wd/ce/requests.html'

        form = DropWDRequestForm()
        can_submit_new_request = True
        url_prefix = 'ce'

    elif user_has_instructor_role(request.user):
        menu = draw_menu(INSTRUCTOR_MENU, 'drop_wd_requests', 'drop_wd_requests', 'instructor')
        template = 'drop_wd/instructor/requests.html'

        from cis.settings.instructor_portal import instructor_portal as portal_lang
        intro = portal_lang(request).from_db().get('drop_wd_requests_blurb', 'Change me')

        form = DropWDRequestForm()
        can_submit_new_request = DropWDRequest.can_instructor_submit_request()
        needs_to_approve = DropWDRequest.needs_instructor_approval()
        url_prefix = 'instructor'

    elif user_has_highschool_admin_role(request.user):
        menu = draw_menu(HS_ADMIN_MENU, 'drop_wd_requests', 'drop_wd_requests', 'highschool_admin')
        template = 'drop_wd/highschool_admin/requests.html'

        from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang
        intro = portal_lang(request).from_db().get('drop_wd_requests_blurb', 'Change me')

        form = DropWDRequestForm()
        can_submit_new_request = DropWDRequest.can_administrator_submit_request()
        needs_to_approve = DropWDRequest.needs_administrator_approval()
        url_prefix = 'highschool_admin'

    elif user_has_student_role(request.user):
        menu = draw_menu(STUDENT_MENU, 'drop_wd_requests', 'drop_wd_requests', 'student')
        template = 'drop_wd/student/requests.html'
    
        form = StudentDropWDRequestForm(student=request.user.student)

        can_submit_new_request = DropWDRequest.can_student_submit_request()
        needs_to_approve = DropWDRequest.needs_student_approval()
        url_prefix = 'student'
    
    return render(
        request,
        template, {
            'menu': menu,
            'page_title': 'Drop/WD Requests',
            'drop_wd_intro': page_settings.get('intro'),
            'submit_new_intro': page_settings.get('submit_new_intro'),
            'can_submit_new_request': can_submit_new_request,
            'needs_to_approve': needs_to_approve,
            'url_prefix': url_prefix,
            # this is hard-coded
            'api_url': '/instructor/drop_wd/api/requests/?format=datatables',            
            'intro': intro,
            'submit_new_drop_request_form': form,
            'terms': Term.objects.all().order_by('-code')
        }
    )

def parent_signature(request, record_id):
    """
    Called when a parent signature is needed
    """
    from cis.forms.student import ParentConsentVerificationForm

    record = get_object_or_404(DropWDRequest, pk=record_id)
    
    template = 'drop_wd/student/parent-sign-consent.html'
    student = record.registration.student
    term = record.registration.class_section.term

    form = ParentConsentVerificationForm(initial={
        'student': student.id,
        'term': term.id
    })
    
    if request.method == 'POST':
        if request.POST.get('action') == 'review_request':
            review_req_form = RequestReviewForm(request.POST)
            if review_req_form.is_valid():
                data = review_req_form.cleaned_data

                if data.get('review_decision') == '1':
                    status = 'Approved'
                else:
                    status = 'Not Approved'

                record.parent_signature = status
                record.notes['parent_note'] = data.get('note', '')

                record.save()

                record = review_req_form.save(request, record)
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Successfully saved your decision.',
                    'list-group-item-success'
                )
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Please fix the error(s) and try again.',
                    'list-group-item-danger'
                )
    
            needs_to_approve = False
            needs_to_approve = record.record_needs_parent_approval()

            edit_request_form = EditDropWDRequestForm(
                record
            )
            review_req_form = RequestReviewForm()
            return render(
                request,
                template, {
                    'student_form': DropWDSignatureForm(
                        initial={
                            'id':record.id,
                            'signature_type': 'student'
                        }),
                    'parent_form': DropWDSignatureForm(
                        initial={
                            'id':record.id,
                            'signature_type': 'parent'
                        }),
                    'review_request_form': review_req_form,
                    'needs_to_approve': needs_to_approve,
                    'record': record,
                    'edit_request_form': edit_request_form,
                    'student': record.registration.student,
                    'registration': record.registration
                })
        elif request.POST.get('submit_for_verification') == 'Submit For Verification':
            form = ParentConsentVerificationForm(request.POST)

            if form.is_valid():
                dob = form.cleaned_data['student_dob']
                zipcode = form.cleaned_data['student_zip']

                if student.user.date_of_birth.strftime('%m/%d/%Y') == dob and zipcode == student.user.postal_code:

                    needs_to_approve = False
                    needs_to_approve = record.record_needs_parent_approval()

                    edit_request_form = EditDropWDRequestForm(
                        record
                    )

                    review_req_form = RequestReviewForm()
                    return render(
                        request,
                        template, {
                            'student_form': DropWDSignatureForm(
                                initial={
                                    'id':record.id,
                                    'signature_type': 'student'
                                }),
                            'parent_form': DropWDSignatureForm(
                                initial={
                                    'id':record.id,
                                    'signature_type': 'parent'
                                }),
                            'review_request_form': review_req_form,
                            'needs_to_approve': needs_to_approve,
                            'record': record,
                            'edit_request_form': edit_request_form,
                            'student': record.registration.student,
                            'registration': record.registration
                        })
                else:
                    messages.add_message(
                        request,
                        messages.SUCCESS,
                        f'The information you entered did not match. Please try again.',
                        'list-group-item-danger')
            else:
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    f'Please fix the error(s) and try again.',
                    'list-group-item-danger'
                )

    return render(
        request,
        template, {
            'form': form,
            'term': term,
            'student': student,
            'message': {
                # 'request_consent': ParentConsent.get_form_message(),                
            }
        })
parent_signature.login_required = False

@require_POST
def send_parent_email(request, record_id):
    """
    Sends an approval email to the parent for a specific Drop/WD request.
    """
    try:
        
        record = get_object_or_404(DropWDRequest, pk=record_id)
    
        if record.record_needs_parent_approval():
            record.request_parent_approval_notification()
            
            return JsonResponse({
                'status': 'success', 
                'message': 'Parent approval email sent successfully.'
            })
        else:
            return JsonResponse({
                'status': 'info', 
                'message': 'Parent approval is not required for this request.'
            })

    except Exception as e:
        return JsonResponse({
            'status': 'error', 
            'message': f'An error occurred: {str(e)}'
        })

def drop_summary_view(request):
    """
    Retrieves and summarizes data on course drop requests for a staff dashboard.
    """
    terms = Term.objects.all().order_by('-code')
    selected_term = request.GET.get('term_id')
    if not selected_term and terms.exists():
        selected_term = terms.first().id
    
    configs = drop_wd_settings.from_db()

    base_queryset = DropWDRequest.objects.filter(
        registration__class_section__term__id=selected_term
    )
    
    user = request.user
    if user_has_highschool_admin_role(user):
        try:
            hsadmin = HSAdministrator.objects.get(user__id=user.id)
            highschools = hsadmin.get_highschools()
            base_queryset = base_queryset.filter(
                registration__student__highschool__id__in=highschools.values_list('id', flat=True)
            )
        except HSAdministrator.DoesNotExist:
            base_queryset = DropWDRequest.objects.none()
    elif user_has_cis_role(user):
        pass
    else:
        return render(request, '403.html', status=403)

    processed_drops = base_queryset.filter(status='processed').count()
    requested_drops = base_queryset.filter(status='requested').count()
    
    drops_by_high_school = base_queryset.filter(status__in=['processed', 'requested']).values(
        'registration__student__highschool__name'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    drops_by_course = base_queryset.filter(status__in=['processed', 'requested']).values(
        'registration__class_section__course__name'
    ).annotate(
        total=Count('id')
    ).order_by('-total')

    menu = draw_menu(cis_menu, 'students', 'drop_wd_requests', 'ce')
    context = {
        'menu': menu,
        'processed_drops': processed_drops,
        'requested_drops': requested_drops,
        'drops_by_high_school': drops_by_high_school,
        'drops_by_course': drops_by_course,
        'term_settings': configs,
        'terms': terms,
        'selected_term': selected_term,
    }

    return render(request, 'drop_wd/ce/summary.html', context)
