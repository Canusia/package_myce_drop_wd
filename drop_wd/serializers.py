from rest_framework import serializers

from cis.serializers.highschool_admin import CustomUserSerializer
from cis.serializers.registration import StudentRegistrationSerializer

from .models import DropWDRequest


class GroupCountSerializer(serializers.Serializer):
    key = serializers.CharField(allow_null=True)
    label = serializers.CharField(allow_null=True, required=False)
    count = serializers.IntegerField()

class DropWDMetricsSerializer(serializers.Serializer):
    by_status = GroupCountSerializer(many=True)
    by_course = GroupCountSerializer(many=True)
    by_highschool = GroupCountSerializer(many=True)
    pending_signatures = serializers.DictField()
    
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
