import logging

from django.contrib import messages
from django.http import JsonResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.views.decorators.clickjacking import xframe_options_exempt

from rest_framework import viewsets

from cis.serializers.class_section import ClassSectionSerializer
from cis.serializers.registration import StudentRegistrationSerializer

from cis.models.term import Term

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

from .models import DropWDRequest
from .forms import DropWDRequestForm, DropWDSignatureForm, EditDropWDRequestForm, StudentDropWDRequestForm, RequestReviewForm
from .serializers import DropWDRequestSerializer


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
    template_name = 'drop_wd/start_request.html'
    
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

def do_bulk_action(request):

    action = request.GET.get('action')
    ids = request.GET.getlist('ids[]')
    
    if action == 'mark_as_approved':
        if user_has_instructor_role(request.user):
            reqs = DropWDRequest.objects.filter(
                id__in=ids,
            )

            reqs.update(
                instructor_signature='Approved'
            )
            return JsonResponse({
                'message': 'Successfully marked as approved',
                'status': 'success'
            })
        
        elif user_has_highschool_admin_role(request.user):
            reqs = DropWDRequest.objects.filter(
                id__in=ids,
            )

            reqs.update(
                counselor_signature='Approved'
            )
            return JsonResponse({
                'message': 'Successfully marked as approved',
                'status': 'success'
            })
        
        elif user_has_student_role(request.user):
            reqs = DropWDRequest.objects.filter(
                id__in=ids,
            )

            reqs.update(
                student_signature='Approved'
            )
            return JsonResponse({
                'message': 'Successfully marked as approved',
                'status': 'success'
            })

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

    from drop_wd.settings.drop_wd_email import drop_wd_email as drop_wd_settings

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
