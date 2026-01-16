from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Student, Lesson, Task, Invoice, FinancialEntry, UserProfile


class StudentSerializer(serializers.ModelSerializer):
    contract_pdf_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = [
            "id",
            "name",
            "guardians",
            "phone",
            "address",
            "plan_name",
            "lessons_total",
            "lessons_done",
            "pix_key",
            "active",
            "contract_pdf",
            "contract_pdf_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["contract_pdf_url"]
    
    def get_contract_pdf_url(self, obj):
        if obj.contract_pdf:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.contract_pdf.url)
            return obj.contract_pdf.url
        return None
    
    def update(self, instance, validated_data):
        # Permite remover o arquivo enviando string vazia ou None
        if 'contract_pdf' in validated_data:
            contract_value = validated_data.get('contract_pdf')
            # Se for string vazia, arquivo vazio, ou None, remove o arquivo
            if contract_value == "" or contract_value is None or (hasattr(contract_value, 'size') and contract_value.size == 0):
                if instance.contract_pdf:
                    instance.contract_pdf.delete(save=False)
                validated_data['contract_pdf'] = None
        return super().update(instance, validated_data)


class LessonSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = Lesson
        fields = [
            "id",
            "student",
            "student_name",
            "date",
            "time",
            "title",
            "info",
            "status",
            "created_at",
            "updated_at",
        ]


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "status",
            "tags",
            "date",
            "due_date",
            "notes",
            "created_at",
            "updated_at",
        ]

class InvoiceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "student",
            "student_name",
            "month",
            "due_date",
            "amount",
            "status",
            "notes",
        ]


class FinancialEntrySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = FinancialEntry
        fields = [
            "id",
            "student",
            "student_name",
            "description",
            "amount",
            "installments",
            "current_installment",
            "issue_date",
            "due_date",
            "payment_date",
            "status",
            "payment_method",
            "notes",
            "created_at",
            "updated_at",
        ]


class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "is_admin",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["date_joined"]

    def get_is_admin(self, obj):
        try:
            return obj.profile.is_admin
        except UserProfile.DoesNotExist:
            return False

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        is_admin = validated_data.pop('is_admin', False)
        
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        
        # Cria ou atualiza o perfil
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.is_admin = is_admin
        profile.save()
        
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        is_admin = validated_data.pop('is_admin', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        
        # Atualiza perfil
        if is_admin is not None:
            profile, created = UserProfile.objects.get_or_create(user=instance)
            profile.is_admin = is_admin
            profile.save()
        
        return instance
