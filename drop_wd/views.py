import logging
import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import JsonResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.urls import NoReverseMatch, reverse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

from rest_framework import viewsets

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
from .serializers import (
    DropWDRequestSerializer,
    DropdownClassSectionSerializer,
    DropdownRegistrationSerializer
)
from .settings.drop_wd_email import drop_wd_email as drop_wd_settings
from .scoping import (
    CE, INSTRUCTOR, HIGHSCHOOL_ADMIN, STUDENT, ROLES, SIGNATURE_FIELDS,
    acting_role,
    registrations_for,
    requests_for,
    user_has_role,
)


logger = logging.getLogger(__name__)

class ClassRegistrationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DropdownRegistrationSerializer
    permission_classes = [INSTRUCTOR_user_only|CIS_user_only|HSADMIN_user_only|STUDENT_user_only]

    # Feeds the student <select> on the New Request page via plain $.getJSON,
    # which reads page 1 and never follows `next`. The project-wide
    # DatatablesPageNumberPagination falls back to PAGE_SIZE = 50 for
    # non-datatables requests and offers no page_size query param, so a
    # section's 51st student was silently unreachable. There is no paging UI
    # here to serve and no other consumer, so return the lot -- which is only
    # affordable because DropdownRegistrationSerializer is lean; see
    # serializers.py before widening it back to cis's nested serializer.
    pagination_class = None

    def get_queryset(self):
        class_section = self.request.GET.get('class_section', '').strip()
        term = self.request.GET.get('term', '').strip()

        user = self.request.user

        try:
            allowed_statuses = drop_wd_settings.get_allowed_registration_statuses()

            records = StudentRegistration.objects.filter(
                class_section__term__id=term,
                class_section__id=class_section
            ).select_related('student__user')

            if allowed_statuses:
                records = records.filter(status__in=allowed_statuses)

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
    serializer_class = DropdownClassSectionSerializer
    permission_classes = [INSTRUCTOR_user_only|CIS_user_only|HSADMIN_user_only|STUDENT_user_only]

    # Same dropdown feeder, same cap: an instructor or HS admin with more than
    # 50 sections in a term could not select the 51st. See above.
    pagination_class = None

    def get_queryset(self):
        term = self.request.GET.get('term', '').strip()
        user = self.request.user

        try:
            allowed_section_statuses = drop_wd_settings.get_allowed_class_section_statuses()

            records = ClassSection.objects.filter(
                term__id=term
            ).select_related('course')

            if allowed_section_statuses:
                records = records.filter(status__in=allowed_section_statuses)
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

        # Every portal reads this one feed (/instructor/drop_wd/api/requests/).
        # `portal` names the page asking, so its rows match what that portal's
        # detail page and bulk action will accept; without it, the union of
        # the user's roles.
        portal = self.request.GET.get('portal', '').strip()
        if portal in ROLES:
            records = requests_for(user, role=portal)
        else:
            records = requests_for(user)

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

def _submitting_roles(user):
    """Roles the user holds that may currently start a request."""
    allowed = {
        CE: True,
        INSTRUCTOR: DropWDRequest.can_instructor_submit_request(),
        HIGHSCHOOL_ADMIN: DropWDRequest.can_administrator_submit_request(),
        STUDENT: DropWDRequest.can_student_submit_request(),
    }
    return [role for role in ROLES if allowed[role] and user_has_role(user, role)]


def submit_request(request):
    """
    Called when a new request is started. Could be initiated by teacher, counselor, or student
    """
    template_name = 'drop_wd/start_request.html'

    if not (
        user_has_cis_role(request.user) or
        (user_has_instructor_role(request.user) and DropWDRequest.can_instructor_submit_request()) or
        (user_has_highschool_admin_role(request.user) and DropWDRequest.can_administrator_submit_request()) or
        (user_has_student_role(request.user) and DropWDRequest.can_student_submit_request())
    ):
        return JsonResponse({
            'title': 'Not allowed',
            'message': 'You are not allowed to submit drop requests.',
            'status': 'error'
        }, status=403)

    if request.method == 'POST':
        if user_has_student_role(request.user):
            form = StudentDropWDRequestForm(student=request.user.student, data=request.POST)
        else:
            form = DropWDRequestForm(data=request.POST)

        if form.is_valid() and not registrations_for(
                request.user, roles=_submitting_roles(request.user)).filter(
                pk=form.cleaned_data['registration'].pk).exists():
            # The form's registration queryset is built from the posted id,
            # so it accepts any registration; only file for one inside the
            # scope of a role that may submit (#8).
            return JsonResponse({
                'title': 'Not allowed',
                'message': 'You are not allowed to submit a request for this registration.',
                'status': 'error'
            }, status=403)

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

@require_POST
def do_bulk_action(request):
    """Bulk approve, as the portal the request was posted through (#10, #13).

    Writes only that role's signature, and only on rows in that role's own
    scope -- not the union of every role the user holds. Ids outside it are
    skipped and counted.
    """
    action = request.POST.get('action')
    ids = request.POST.getlist('ids[]')

    if action != 'mark_as_approved':
        return JsonResponse({
            'message': 'Unknown action.',
            'status': 'error'
        }, status=400)

    role = acting_role(request)
    field = SIGNATURE_FIELDS.get(role)
    if field is None:
        return JsonResponse({
            'message': 'You are not allowed to approve requests here.',
            'status': 'error'
        }, status=403)

    valid_ids = set()
    for value in ids:
        try:
            valid_ids.add(uuid.UUID(str(value)))
        except ValueError:
            pass

    updated = requests_for(request.user, role=role).filter(
        id__in=valid_ids
    ).update(**{field: 'Approved'})
    skipped = len(set(ids)) - updated

    message = f'Successfully marked {updated} request(s) as approved.'
    if skipped:
        message += f' {skipped} request(s) were skipped because you cannot approve them.'

    return JsonResponse({
        'message': message,
        'status': 'success' if updated else 'error',
        'updated': updated,
        'skipped': skipped,
    })

@xframe_options_exempt
def drop_request(request, record_id):

    # The portal the page is served from decides the role, and the record
    # must be inside that role's own scope -- not the union of the user's
    # roles, or a teacher who is also an HS admin could sign as instructor for
    # a colleague's section (#12). 404 rather than 403, so ids can't be probed.
    role = acting_role(request)
    if role is None:
        raise Http404
    record = get_object_or_404(requests_for(request.user, role=role), pk=record_id)
    needs_to_approve = False

    if role == CE:
        template = 'drop_wd/ce/request.html'

    elif role == INSTRUCTOR:
        template = 'drop_wd/instructor/request.html'
        needs_to_approve = record.record_needs_instructor_approval()

    elif role == HIGHSCHOOL_ADMIN:
        template = 'drop_wd/highschool_admin/request.html'
        # The HS admin signs as counselor, so it is the counselor approval
        # that is pending (was record_needs_student_approval).
        needs_to_approve = record.record_needs_administrator_approval()

    else:
        template = 'drop_wd/student/request.html'
        needs_to_approve = record.record_needs_student_approval()

    # Student and parent signatures come from the student only (#14).
    can_sign_as_student = record.registration.student.user_id == request.user.id

    edit_request_form = EditDropWDRequestForm(
        record
    )

    review_req_form = RequestReviewForm()

    if request.method == 'POST':
        if request.POST.get('action') == 'review_request':
            review_req_form = RequestReviewForm(request.POST)
            if not needs_to_approve:
                # Only the role whose approval is pending, on its own page.
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'Your review is not needed on this request.',
                    'list-group-item-danger'
                )
            elif review_req_form.is_valid():
                record = review_req_form.save(request, record, role=role)
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
            # Edits the registration itself; only the CE page renders it.
            if role != CE:
                raise Http404
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

            if not can_sign_as_student or \
                    request.POST.get('signature_type') not in ('student', 'parent'):
                messages.add_message(
                    request,
                    messages.SUCCESS,
                    'You are not allowed to sign this request.',
                    'list-group-item-danger'
                )
            elif form.is_valid():
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
            'can_sign_as_student': can_sign_as_student,
            'record': record,
            'edit_request_form': edit_request_form,
            'student': record.registration.student,
            'registration': record.registration
        })

@require_POST
def send_processed_email(request, record_id):
    if not user_has_cis_role(request.user):
        raise Http404
    record = get_object_or_404(DropWDRequest, pk=record_id)
    try:
        private_note = request.POST.get('private_note', '').strip()

        if private_note:
            record.registration.student.add_note(
                createdby=request.user,
                note=private_note,
                meta={
                    'type': 'private',
                    'private_note': private_note,
                    'registration_id': str(record.registration.id)
                }
            )

        record.send_processed_notification()
        return JsonResponse({
            'status': 'success',
            'message': 'Processed notification email sent successfully.'
        })
    except Exception as e:
        logger.error(e)
        return JsonResponse({
            'status': 'error',
            'message': 'Unable to send email. ' + str(e)
        }, status=400)

@require_POST
def delete_record(request, record_id):
    if not user_has_cis_role(request.user):
        raise Http404
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
    # The portal the page is served from, not the first role the user holds:
    # a teacher who is also an HS admin gets the HS admin page under
    # /highschool_admin/.
    role = acting_role(request)
    academic_years = []
    if role == CE:
        from cis.models.term import AcademicYear
        academic_years = AcademicYear.objects.all().order_by('-name')  # Summary tab filter
        menu = draw_menu(cis_menu, 'students', 'drop_wd_requests', 'ce')
        template = 'drop_wd/ce/requests.html'

        form = DropWDRequestForm()
        can_submit_new_request = True
        url_prefix = 'ce'

    elif role == INSTRUCTOR:
        menu = draw_menu(INSTRUCTOR_MENU, 'drop_wd_requests', 'drop_wd_requests', 'instructor')
        template = 'drop_wd/instructor/requests.html'

        from .portal_text import portal_text
        intro = portal_text('instructor').get('drop_wd_requests_blurb', 'Change me')

        form = DropWDRequestForm()
        can_submit_new_request = DropWDRequest.can_instructor_submit_request()
        needs_to_approve = DropWDRequest.needs_instructor_approval()
        url_prefix = 'instructor'

    elif role == HIGHSCHOOL_ADMIN:
        menu = draw_menu(HS_ADMIN_MENU, 'drop_wd_requests', 'drop_wd_requests', 'highschool_admin')
        template = 'drop_wd/highschool_admin/requests.html'

        from cis.settings.highschool_admin_portal import highschool_admin_portal as portal_lang
        intro = portal_lang(request).from_db().get('drop_wd_requests_blurb', 'Change me')

        form = DropWDRequestForm()
        can_submit_new_request = DropWDRequest.can_administrator_submit_request()
        needs_to_approve = DropWDRequest.needs_administrator_approval()
        url_prefix = 'highschool_admin'

    elif role == STUDENT:
        menu = draw_menu(STUDENT_MENU, 'drop_wd_requests', 'drop_wd_requests', 'student')
        template = 'drop_wd/student/requests.html'
    
        form = StudentDropWDRequestForm(student=request.user.student)

        can_submit_new_request = DropWDRequest.can_student_submit_request()
        needs_to_approve = DropWDRequest.needs_student_approval()
        url_prefix = 'student'

    else:
        raise Http404

    # this is hard-coded (unchanged here — the endpoint stays the instructor one);
    # `portal` scopes the rows to this page's role.
    api_url = f'/instructor/drop_wd/api/requests/?format=datatables&portal={role}'

    try:
        bulk_actions_url = reverse(f'{url_prefix}_drop_wd:bulk_actions')
    except NoReverseMatch:
        bulk_actions_url = ''

    from .services import get_requests_table_config
    requests_table_config = get_requests_table_config().build_config(
        variant='portal_approver' if needs_to_approve else 'portal',
        api_url=api_url,
        details_prefix=f'/{url_prefix}/drop_wd/request/',
        filter_form_selector='#all_req_filter',
    )

    return render(
        request,
        template, {
            'menu': menu,
            'page_title': 'Drop/WD Requests',
            'drop_wd_intro': page_settings.get('intro'),
            'submit_new_intro': page_settings.get('submit_new_intro'),
            'can_submit_new_request': can_submit_new_request,
            'drops_permitted': bool(drop_wd_settings.get_allowed_terms()),
            'needs_to_approve': needs_to_approve,
            'url_prefix': url_prefix,
            'api_url': api_url,
            'bulk_actions_url': bulk_actions_url,
            'intro': intro,
            'submit_new_drop_request_form': form,
            'terms': Term.objects.all().order_by('-code'),
            'academic_years': academic_years,
            'requests_table': requests_table_config,
        }
    )


# --- Summary tab -------------------------------------------------------------
# The aggregation lives in summary.py, shared with the summary report (#6).

@xframe_options_exempt
def requests_summary(request):
    """JSON aggregates for the CE Summary tab.

    Client-side tables rather than a server-side DataTables feed: the result
    sets are small (one row per term / school / course), and it means CSV and
    PDF exports carry every row instead of only the page on screen.
    """
    if not user_has_cis_role(request.user):
        raise Http404

    from django.db.models.functions import TruncMonth

    from .summary import breakdowns

    term_ids = [t for t in request.GET.getlist('term') if t]
    academic_year_ids = [a for a in request.GET.getlist('academic_year') if a]

    records = DropWDRequest.objects.all()
    try:
        if term_ids:
            records = records.filter(
                registration__class_section__term__id__in=term_ids)
        if academic_year_ids:
            records = records.filter(
                registration__class_section__term__academic_year__id__in=academic_year_ids)
        total = records.count()
    except (ValueError, ValidationError):  # a malformed id
        records = DropWDRequest.objects.none()
        total = 0

    by_month = (
        records
        .annotate(month=TruncMonth('created_on'))
        .values('month')
        .order_by('month')
        .annotate(total=Count('id'))
    ) if total else []

    payload = {
        'headline': {
            'total': total,
            'requested': records.filter(status='requested').count(),
            'processed': records.filter(status='processed').count(),
            'highschools': records.values(
                'registration__student__highschool').distinct().count(),
            'courses': records.values(
                'registration__class_section__course').distinct().count(),
        },
        'breakdowns': breakdowns(records, total=total),
        'by_month': [
            {'month': row['month'].strftime('%b %Y') if row['month'] else '',
             'total': row['total']}
            for row in by_month
        ],
    }
    return JsonResponse(payload)
