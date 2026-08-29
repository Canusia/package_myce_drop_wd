from rest_framework import serializers

from cis.serializers.highschool_admin import CustomUserSerializer
from cis.serializers.registration import StudentRegistrationSerializer

from .models import DropWDRequest


# --- Dropdown feeders -------------------------------------------------------
#
# The two "New Request" <select> endpoints are unpaginated (see views.py), so
# they must not carry the cost of cis's full nested serializers.
# StudentRegistrationSerializer embeds ClassSectionSerializer, which in turn
# embeds course -> campus/location, teacher, term -> academic_year, highschool
# and the syllabi set; serializing 60 registrations with it cost 1,571 queries
# and 390 KB, of which the templates read four values. These lean serializers
# emit exactly the fields the templates consume, in the same nested shape.


class DropdownUserSerializer(serializers.Serializer):
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)


class DropdownStudentSerializer(serializers.Serializer):
    user = DropdownUserSerializer(read_only=True)


class DropdownRegistrationSerializer(serializers.Serializer):
    """Shape consumed by load_class_registrations() in start_request.html."""

    id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    status_pretty = serializers.CharField(source='get_status', read_only=True)
    student = DropdownStudentSerializer(read_only=True)


class DropdownCourseSerializer(serializers.Serializer):
    name = serializers.CharField(read_only=True)


class DropdownClassSectionSerializer(serializers.Serializer):
    """Shape consumed by load_class_sections() in start_request.html."""

    id = serializers.UUIDField(read_only=True)
    class_number = serializers.CharField(read_only=True)
    course = DropdownCourseSerializer(read_only=True)


class DropWDRequestSerializer(serializers.ModelSerializer):
    registration = StudentRegistrationSerializer()

    created_on = serializers.DateTimeField(format='%m/%d/%Y %I:%M %p')
    created_by = CustomUserSerializer()
    
    has_student_signature = serializers.CharField(
        read_only=True
    )

    next_step = serializers.CharField(
        read_only=True
    )
    
    sexy_status = serializers.CharField(
        read_only=True
    )

    has_parent_signature = serializers.CharField(
        read_only=True
    )

    has_instructor_signature = serializers.CharField(
        read_only=True
    )

    has_counselor_signature = serializers.CharField(
        read_only=True
    )

    approvals = serializers.CharField(
        read_only=True
    )

    class Meta:
        model = DropWDRequest
        fields = '__all__'

        datatables_always_serialize = [
            'id',
            'created_on',
            'student_signature',
            'parent_signature',
            'instructor_signature',
            'couselor_signature',
            'sexy_status',
            'next_step',
        ]
