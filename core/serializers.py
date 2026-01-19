from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Student, Lesson, Task, Invoice, FinancialEntry, UserProfile, LessonPlan, BillingLog


class StudentSerializer(serializers.ModelSerializer):
    contract_pdf_url = serializers.SerializerMethodField()
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    
    class Meta:
        model = Student
        fields = [
            "id",
            "name",
            "guardians",
            "phone",
            "address",
            "email",
            "status",
            "plan_name",
            "plan_start_date",
            "lessons_total",
            "lessons_done",
            "default_due_day",
            "preferred_payment_method",
            "pix_key",
            "contract_pdf",
            "contract_pdf_url",
            "user",
            "user_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["contract_pdf_url", "user"]
    
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
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Lesson
        fields = [
            "id",
            "student",
            "student_name",
            "user",
            "user_username",
            "date",
            "time",
            "title",
            "info",
            "status",
            "created_at",
            "updated_at",
        ]


class TaskSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

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
            "user",
            "user_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user"]

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
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    beneficiary_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),  # Queryset inicial, será filtrado no __init__
        required=False,
        help_text="Professor que receberá o lançamento"
    )
    beneficiary_username = serializers.CharField(source="beneficiary_user.username", read_only=True)

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
            "user",
            "user_username",
            "beneficiary_user",
            "beneficiary_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define o queryset do beneficiary_user baseado no request
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            try:
                if user.profile.user_profile == UserProfile.PROFILE_TEACHER:
                    # Professor pode escolher ele mesmo ou seus parceiros
                    partner_ids = list(user.profile.partner_teachers.values_list('user_id', flat=True))
                    partner_ids.append(user.id)
                    self.fields['beneficiary_user'].queryset = User.objects.filter(id__in=partner_ids)
                else:
                    # Prof. Parceiro só pode escolher ele mesmo
                    self.fields['beneficiary_user'].queryset = User.objects.filter(id=user.id)
            except UserProfile.DoesNotExist:
                self.fields['beneficiary_user'].queryset = User.objects.filter(id=user.id)


class LessonPlanSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    links_list = serializers.SerializerMethodField()
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = LessonPlan
        fields = [
            "id",
            "student",
            "student_name",
            "date",
            "links",
            "links_list",
            "goals",
            "user",
            "user_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["links_list", "user"]

    def get_links_list(self, obj):
        """Retorna os links como uma lista"""
        return obj.get_links_list()


class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.SerializerMethodField()
    user_profile = serializers.SerializerMethodField()
    partner_teachers = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)
    user_profile_write = serializers.ChoiceField(
        choices=UserProfile.PROFILE_CHOICES,
        write_only=True,
        required=True
    )
    partner_teachers_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_null=True,
        allow_empty=True
    )

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
            "user_profile",
            "partner_teachers",
            "user_profile_write",
            "partner_teachers_ids",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["date_joined", "user_profile", "partner_teachers"]

    def get_is_admin(self, obj):
        try:
            return obj.profile.is_admin
        except UserProfile.DoesNotExist:
            return False

    def get_user_profile(self, obj):
        try:
            return obj.profile.user_profile
        except UserProfile.DoesNotExist:
            return None

    def get_partner_teachers(self, obj):
        try:
            partner_teachers = obj.profile.partner_teachers.all()
            return [
                {
                    "id": teacher.user.id,
                    "username": teacher.user.username,
                    "email": teacher.user.email,
                }
                for teacher in partner_teachers
            ]
        except UserProfile.DoesNotExist:
            return []

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        is_admin = validated_data.pop('is_admin', False)
        user_profile = validated_data.pop('user_profile_write', UserProfile.PROFILE_TEACHER)
        partner_teachers_ids = validated_data.pop('partner_teachers_ids', [])
        
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        
        # Cria ou atualiza o perfil
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.is_admin = is_admin
        profile.user_profile = user_profile
        profile.save()
        
        # Vincula professores parceiros
        if partner_teachers_ids:
            partner_profiles = UserProfile.objects.filter(
                user_id__in=partner_teachers_ids,
                user_profile=UserProfile.PROFILE_PARTNER_TEACHER
            )
            profile.partner_teachers.set(partner_profiles)
        
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        is_admin = validated_data.pop('is_admin', None)
        user_profile = validated_data.pop('user_profile_write', None)
        partner_teachers_ids = validated_data.pop('partner_teachers_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        
        # Atualiza perfil
        profile, created = UserProfile.objects.get_or_create(user=instance)
        if is_admin is not None:
            profile.is_admin = is_admin
        if user_profile is not None:
            profile.user_profile = user_profile
        profile.save()
        
        # Atualiza professores parceiros
        if partner_teachers_ids is not None:
            if partner_teachers_ids:
                partner_profiles = UserProfile.objects.filter(
                    user_id__in=partner_teachers_ids,
                    user_profile=UserProfile.PROFILE_PARTNER_TEACHER
                )
                profile.partner_teachers.set(partner_profiles)
            else:
                profile.partner_teachers.clear()
        
        return instance


class BillingLogSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="financial_entry.student.name", read_only=True)
    financial_entry_id = serializers.IntegerField(source="financial_entry.id", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    message_type_display = serializers.CharField(source="get_message_type_display", read_only=True)
    send_method_display = serializers.CharField(source="get_send_method_display", read_only=True)
    
    class Meta:
        model = BillingLog
        fields = [
            "id",
            "financial_entry",
            "financial_entry_id",
            "student_name",
            "user",
            "user_username",
            "message_type",
            "message_type_display",
            "send_method",
            "send_method_display",
            "message_content",
            "sent_at",
        ]
        read_only_fields = ["user", "sent_at"]
