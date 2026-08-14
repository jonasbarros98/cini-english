from rest_framework import serializers
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Student, Lesson, Invoice, FinancialEntry, UserProfile, LessonPlan, LessonPlanAttachment, BillingLog, Subscription, TeacherMaterial
from .models import StudentHomework, StudentHomeworkMessage
from rest_framework import serializers as drf_serializers


def _assignable_teacher_ids(request):
    """IDs de usuários que o dono da conta pode atribuir como professor do aluno (ele + parceiros)."""
    if not request or not request.user.is_authenticated:
        return []
    try:
        if request.user.profile.user_profile != UserProfile.PROFILE_TEACHER:
            return [request.user.id]
        partner_ids = list(request.user.profile.partner_teachers.values_list("user_id", flat=True))
        partner_ids.append(request.user.id)
        return partner_ids
    except UserProfile.DoesNotExist:
        return [request.user.id]


class StudentSerializer(serializers.ModelSerializer):
    contract_pdf_url = serializers.SerializerMethodField()
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    assigned_teacher_name = serializers.SerializerMethodField()
    assigned_teacher = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    # Fim de pacote: calculado aqui para a tela não repetir a regra em JS e
    # as duas versões divergirem. `lessons_remaining` é None quando o aluno
    # não tem pacote com número fechado de aulas.
    lessons_remaining = serializers.IntegerField(read_only=True, allow_null=True)
    package_ending = serializers.SerializerMethodField()
    lesson_alert_at = serializers.SerializerMethodField()

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
            "billing_type",
            "plan_name",
            "level",
            "teacher_notes",
            "plan_start_date",
            "lessons_total",
            "lessons_done",
            "monthly_amount",
            "per_lesson_amount",
            "default_due_day",
            "preferred_payment_method",
            "pix_key",
            "contract_pdf",
            "contract_pdf_url",
            "user",
            "user_username",
            "assigned_teacher",
            "assigned_teacher_name",
            "lesson_alert_threshold",
            "lessons_remaining",
            "package_ending",
            "lesson_alert_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "contract_pdf_url", "user", "user_username", "assigned_teacher_name",
            "lessons_remaining", "package_ending", "lesson_alert_at",
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        allowed_ids = _assignable_teacher_ids(request)
        if allowed_ids:
            self.fields["assigned_teacher"].queryset = User.objects.filter(id__in=allowed_ids)
    
    def get_assigned_teacher_name(self, obj):
        if not obj.assigned_teacher_id:
            return None
        u = obj.assigned_teacher
        return u.get_full_name() or u.username

    def _padrao_do_professor(self, obj):
        """Padrão de aviso do dono da conta, com fallback se não houver perfil."""
        try:
            perfil = obj.user.profile
        except Exception:
            return 2, True
        return perfil.lesson_alert_default, perfil.lesson_alert_enabled

    def get_package_ending(self, obj):
        padrao, ligado = self._padrao_do_professor(obj)
        if not ligado:
            return False
        return obj.is_package_ending(padrao)

    def get_lesson_alert_at(self, obj):
        padrao, _ = self._padrao_do_professor(obj)
        return obj.lesson_alert_at(padrao)
    
    def validate_assigned_teacher(self, value):
        if value is None or value == "" or (isinstance(value, str) and value.strip() == ""):
            return None
        request = self.context.get("request")
        allowed = _assignable_teacher_ids(request)
        pk = getattr(value, "id", value)
        if allowed and pk not in allowed:
            raise serializers.ValidationError("Professor selecionado não é permitido para esta conta.")
        return value

    def validate_name(self, value):
        name = (value or "").strip()
        # Limite de segurança para evitar estouro de layout na UI.
        if len(name) > 120:
            raise serializers.ValidationError("Nome muito longo. Use no máximo 120 caracteres.")
        return name

    def validate(self, attrs):
        # JSON às vezes reenvia a URL do contrato como string (eco do GET); FileField rejeita → 400.
        # String não vazia: ignorar e manter o PDF atual. String vazia: deixa o update() remover o arquivo.
        if self.instance and "contract_pdf" in attrs:
            v = attrs.get("contract_pdf")
            if isinstance(v, str) and v.strip() != "":
                attrs.pop("contract_pdf", None)
        return super().validate(attrs)

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
            # FormData pode enviar como string vazia ou como arquivo vazio
            if (contract_value == "" or 
                contract_value is None or 
                (hasattr(contract_value, 'size') and contract_value.size == 0) or
                (isinstance(contract_value, str) and contract_value.strip() == "")):
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
            "realized",
            "created_at",
            "updated_at",
        ]


class StudentHomeworkSerializer(serializers.ModelSerializer):
    assigned_by = serializers.PrimaryKeyRelatedField(read_only=True)
    assigned_by_username = serializers.CharField(source="assigned_by.username", read_only=True)
    student_name = serializers.CharField(source="student.name", read_only=True)
    messages = serializers.SerializerMethodField()
    unread_student_messages_count = serializers.SerializerMethodField()

    def get_messages(self, obj):
        return [
            {
                "id": m.id,
                "sender": m.sender,
                "sender_label": "Aluno" if m.sender == StudentHomeworkMessage.SENDER_STUDENT else "Professor",
                "message": m.message,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in obj.messages.all().order_by("created_at", "id")
        ]

    def get_unread_student_messages_count(self, obj):
        """
        Quantas mensagens do aluno ainda não foram marcadas como lidas pelo professor logado.
        Usamos o related_name `reads` do modelo StudentHomeworkMessageRead.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return 0
        # Mensagens enviadas pelo aluno que não possuem registro de "read" para este usuário.
        return (
            obj.messages.filter(sender=StudentHomeworkMessage.SENDER_STUDENT)
            .exclude(reads__user=user)
            .count()
        )

    class Meta:
        model = StudentHomework
        fields = [
            "id",
            "student",
            "student_name",
            "title",
            "description",
            "due_date",
            "status",
            "student_response",
            "teacher_feedback",
            "messages",
            "unread_student_messages_count",
            "assigned_by",
            "assigned_by_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["assigned_by", "assigned_by_username", "student_name", "created_at", "updated_at"]


class TeacherMaterialSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = TeacherMaterial
        fields = [
            "id",
            "user",
            "title",
            "description",
            "material_type",
            "file",
            "file_url",
            "external_url",
            "file_size",
            "file_size_display",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "file_url", "file_size", "file_size_display", "created_at", "updated_at"]

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        rel = reverse("api-arquivos-download", kwargs={"material_id": obj.pk})
        if request:
            return request.build_absolute_uri(rel)
        return rel

    def get_file_size_display(self, obj):
        return obj.get_file_size_display()


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


def _financial_assignable_user_ids(request):
    """IDs de usuários que o dono da conta pode atribuir como professor do lançamento (ele + parceiros)."""
    if not request or not request.user.is_authenticated:
        return []
    try:
        if request.user.profile.user_profile != UserProfile.PROFILE_TEACHER:
            return [request.user.id]
        partner_ids = list(request.user.profile.partner_teachers.values_list("user_id", flat=True))
        partner_ids.append(request.user.id)
        return partner_ids
    except UserProfile.DoesNotExist:
        return [request.user.id]


class FinancialEntrySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        help_text="Professor responsável pelo lançamento (dono da conta pode delegar ao parceiro)"
    )
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_display_name = serializers.SerializerMethodField()
    beneficiary_user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
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
            "user_display_name",
            "beneficiary_user",
            "beneficiary_username",
            "created_at",
            "updated_at",
        ]

    def get_user_display_name(self, obj):
        if not obj.user_id:
            return None
        u = obj.user
        return u.get_full_name() or u.username

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            user = request.user
            try:
                if user.profile.user_profile == UserProfile.PROFILE_TEACHER:
                    partner_ids = list(user.profile.partner_teachers.values_list('user_id', flat=True))
                    partner_ids.append(user.id)
                    qs = User.objects.filter(id__in=partner_ids)
                    self.fields['beneficiary_user'].queryset = qs
                    self.fields['user'].queryset = qs
                else:
                    qs = User.objects.filter(id=user.id)
                    self.fields['beneficiary_user'].queryset = qs
                    self.fields['user'].read_only = True
                    self.fields['user'].queryset = qs
            except UserProfile.DoesNotExist:
                self.fields['beneficiary_user'].queryset = User.objects.filter(id=user.id)
                self.fields['user'].read_only = True
                self.fields['user'].queryset = User.objects.filter(id=user.id)


class LessonPlanAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = LessonPlanAttachment
        fields = [
            "id",
            "file",
            "file_url",
            "original_filename",
            "file_size",
            "file_size_display",
            "uploaded_at",
        ]
        read_only_fields = ["file_url", "file_size_display", "uploaded_at"]

    def get_file_url(self, obj):
        """Retorna a URL do arquivo"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_file_size_display(self, obj):
        """Retorna o tamanho formatado"""
        return obj.get_file_size_display()


class LessonPlanSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    links_list = serializers.SerializerMethodField()
    attachments = LessonPlanAttachmentSerializer(many=True, read_only=True)
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
            "attachments",
            "user",
            "user_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["links_list", "attachments", "user"]

    def get_links_list(self, obj):
        """Retorna os links como uma lista"""
        return obj.get_links_list()

    def to_representation(self, instance):
        """Garante que a data seja retornada como YYYY-MM-DD sem timezone"""
        ret = super().to_representation(instance)
        if 'date' in ret and ret['date']:
            # Se a data vier como string ISO 8601, extrai apenas YYYY-MM-DD
            if isinstance(ret['date'], str):
                ret['date'] = ret['date'].split('T')[0].split(' ')[0]
            # Se vier como objeto date, formata como YYYY-MM-DD
            elif hasattr(ret['date'], 'strftime'):
                ret['date'] = ret['date'].strftime('%Y-%m-%d')
        return ret


class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.SerializerMethodField()
    subscription_exempt = serializers.SerializerMethodField()
    subscription_summary = serializers.SerializerMethodField()
    user_profile = serializers.SerializerMethodField()
    partner_teachers = serializers.SerializerMethodField()
    owner_teacher = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
    user_profile_write = serializers.ChoiceField(
        choices=UserProfile.PROFILE_CHOICES,
        write_only=True,
        required=False
    )
    partner_teachers_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_null=True,
        allow_empty=True
    )
    subscription_exempt_write = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
            "is_admin",
            "subscription_exempt",
            "subscription_summary",
            "user_profile",
            "partner_teachers",
            "owner_teacher",
            "user_profile_write",
            "partner_teachers_ids",
            "subscription_exempt_write",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["date_joined", "user_profile", "partner_teachers", "owner_teacher", "subscription_summary"]

    def get_subscription_summary(self, obj):
        try:
            sub = obj.subscription
            return {
                "tier": sub.tier,
                "tier_display": sub.get_tier_display(),
                "status": sub.status,
                "status_display": sub.get_status_display(),
                "is_active": sub.is_active,
                "current_period_end": sub.current_period_end.strftime("%Y-%m-%d") if sub.current_period_end else None,
            }
        except Subscription.DoesNotExist:
            return None

    def get_is_admin(self, obj):
        try:
            return obj.profile.is_admin
        except UserProfile.DoesNotExist:
            return False

    def get_subscription_exempt(self, obj):
        try:
            return getattr(obj.profile, 'subscription_exempt', False)
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

    def get_owner_teacher(self, obj):
        """Para Prof. Parceiro: retorna o professor dono da conta que o vinculou."""
        try:
            profile = obj.profile
            if profile.user_profile != UserProfile.PROFILE_PARTNER_TEACHER:
                return None
            owner = UserProfile.objects.filter(partner_teachers=profile).select_related("user").first()
            if not owner:
                return None
            u = owner.user
            name = (u.first_name or u.last_name) and f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username
            return {"id": u.id, "username": u.username, "name": name or u.username}
        except UserProfile.DoesNotExist:
            return None

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        password_confirm = validated_data.pop('password_confirm', None)
        is_admin = validated_data.pop('is_admin', False)
        subscription_exempt = validated_data.pop('subscription_exempt_write', False)
        user_profile = validated_data.pop('user_profile_write', UserProfile.PROFILE_TEACHER)
        partner_teachers_ids = validated_data.pop('partner_teachers_ids', [])
        
        # Validar confirmação de senha
        if password:
            if not password_confirm:
                raise serializers.ValidationError({'password_confirm': 'Confirmação de senha é obrigatória quando uma senha é fornecida.'})
            if password != password_confirm:
                raise serializers.ValidationError({'password_confirm': 'As senhas não coincidem.'})
        
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        
        # Cria ou atualiza o perfil
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.is_admin = is_admin
        profile.subscription_exempt = subscription_exempt
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
        subscription_exempt = validated_data.pop('subscription_exempt_write', None)
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
        if subscription_exempt is not None:
            profile.subscription_exempt = subscription_exempt
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


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_display = serializers.CharField(source="get_plan_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            "id",
            "user",
            "user_username",
            "plan",
            "plan_display",
            "status",
            "status_display",
            "is_active",
            "stripe_customer_id",
            "stripe_subscription_id",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "is_active"]


class ProfileSerializer(drf_serializers.ModelSerializer):
    """Serializer para o perfil do usuário (dados editáveis)"""
    username = drf_serializers.CharField(source='user.username', read_only=True)
    email = drf_serializers.EmailField(required=False, allow_blank=True, write_only=True)
    first_name = drf_serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    last_name = drf_serializers.CharField(required=False, allow_blank=True, allow_null=True, write_only=True)
    password = drf_serializers.CharField(write_only=True, required=False, allow_blank=True)
    password_confirm = drf_serializers.CharField(write_only=True, required=False, allow_blank=True)
    photo = drf_serializers.ImageField(required=False, allow_null=True)
    is_admin = drf_serializers.BooleanField(read_only=True)
    user_profile = drf_serializers.CharField(read_only=True)
    role = drf_serializers.SerializerMethodField()
    subscription_status = drf_serializers.SerializerMethodField()
    stripe_customer_id = drf_serializers.SerializerMethodField()
    partner_teachers = drf_serializers.SerializerMethodField()
    partner_teachers_ids = drf_serializers.ListField(
        child=drf_serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    
    slug_publico = drf_serializers.SlugField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=80,
        help_text="Slug único para link público de agendamento (ex: ayla-barros)"
    )
    agenda_publica_ativa = drf_serializers.BooleanField(required=False, default=False)
    public_availability = drf_serializers.JSONField(required=False, default=dict)
    public_booking_duration = drf_serializers.IntegerField(required=False, default=60, min_value=15, max_value=180)
    google_picture_url = drf_serializers.URLField(read_only=True)
    google_hosted_domain = drf_serializers.CharField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm',
            'cpf_cnpj', 'phone', 'cep', 'address', 'city', 'state',
            'timezone', 'language', 'photo',
            'google_picture_url', 'google_hosted_domain',
            'is_admin', 'user_profile', 'role',
            'subscription_status', 'stripe_customer_id',
            'partner_teachers', 'partner_teachers_ids',
            'slug_publico', 'agenda_publica_ativa',
            'public_availability', 'public_booking_duration',
        ]
        read_only_fields = ['is_admin', 'user_profile', 'username', 'google_picture_url', 'google_hosted_domain']
    
    def to_representation(self, instance):
        """Customizar representação para incluir dados do User"""
        representation = super().to_representation(instance)
        # Adicionar dados do User na representação
        representation['email'] = instance.user.email
        representation['first_name'] = instance.user.first_name
        representation['last_name'] = instance.user.last_name
        
        # Garantir que a URL da foto seja absoluta se existir
        if instance.photo:
            representation['photo'] = instance.photo.url
        else:
            representation['photo'] = None
            
        return representation
    
    def get_role(self, obj):
        return "ADMIN" if obj.is_admin else "USER"
    
    def get_subscription_status(self, obj):
        try:
            subscription = obj.user.subscription
            return {
                'plan': subscription.plan,
                'status': subscription.status,
                'is_active': subscription.status == Subscription.STATUS_ACTIVE
            }
        except:
            return {
                'plan': None,
                'status': None,
                'is_active': False
            }
    
    def get_stripe_customer_id(self, obj):
        try:
            subscription = obj.user.subscription
            return subscription.stripe_customer_id or None
        except:
            return None
    
    def get_partner_teachers(self, obj):
        """Lista de professores parceiros vinculados (só para perfil Professor)."""
        try:
            partners = obj.partner_teachers.select_related('user').all()
            return [
                {
                    'id': p.user.id,
                    'username': p.user.username,
                    'name': p.user.get_full_name() or p.user.username,
                    'email': p.user.email or '',
                }
                for p in partners
            ]
        except Exception:
            return []
    
    def validate_slug_publico(self, value):
        """Valida slug único (apenas letras, números, hífens)."""
        if not value or not str(value).strip():
            return None
        slug = str(value).strip().lower()
        if len(slug) < 2:
            raise drf_serializers.ValidationError("O slug deve ter pelo menos 2 caracteres.")
        import re
        if not re.match(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', slug):
            raise drf_serializers.ValidationError("Use apenas letras minúsculas, números e hífens.")
        # Unicidade (excluir o próprio usuário)
        instance = self.instance
        qs = UserProfile.objects.filter(slug_publico=slug)
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise drf_serializers.ValidationError("Este slug já está em uso por outro professor.")
        return slug

    def validate(self, data):
        password = data.get('password', '')
        password_confirm = data.get('password_confirm', '')
        
        if password or password_confirm:
            if password != password_confirm:
                raise drf_serializers.ValidationError({
                    'password_confirm': 'As senhas não coincidem.'
                })
            if len(password) < 8:
                raise drf_serializers.ValidationError({
                    'password': 'A senha deve ter pelo menos 8 caracteres.'
                })
        
        return data
    
    # Removido to_internal_value - a transformação agora é feita na view
    
    def update(self, instance, validated_data):
        user = instance.user
        
        # Extrair dados do User diretamente do validated_data (não mais aninhados)
        email = validated_data.pop('email', None)
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        password = validated_data.pop('password', None)
        password_confirm = validated_data.pop('password_confirm', None)
        photo = validated_data.pop('photo', None)
        partner_teachers_ids = validated_data.pop('partner_teachers_ids', None)
        
        # Atualizar vínculo de professores parceiros (apenas para perfil Professor)
        if instance.user_profile == UserProfile.PROFILE_TEACHER and partner_teachers_ids is not None:
            partner_profiles = UserProfile.objects.filter(
                user_id__in=partner_teachers_ids,
                user_profile=UserProfile.PROFILE_PARTNER_TEACHER,
            )
            instance.partner_teachers.set(partner_profiles)
        
        # Log para debug
        print(f"[DEBUG Serializer] validated_data recebido: {validated_data}")
        print(f"[DEBUG Serializer] email={email}, first_name={first_name}, last_name={last_name}")
        print(f"[DEBUG Serializer] photo recebido: {photo}")
        print(f"[DEBUG Serializer] User antes: email={user.email}, first_name={user.first_name}, last_name={user.last_name}")
        
        # Atualizar dados do User diretamente
        if email is not None:
            user.email = email
            print(f"[DEBUG Serializer] Atualizando email para: {email}")
        if first_name is not None:
            user.first_name = first_name
            print(f"[DEBUG Serializer] Atualizando first_name para: {first_name}")
        if last_name is not None:
            user.last_name = last_name
            print(f"[DEBUG Serializer] Atualizando last_name para: {last_name}")
        
        # Atualizar senha se fornecida
        if password:
            user.set_password(password)
            print(f"[DEBUG Serializer] Senha atualizada")
        
        # Salvar User
        user.save()
        print(f"[DEBUG Serializer] User salvo: email={user.email}, first_name={user.first_name}, last_name={user.last_name}")
        
        # Atualizar dados do UserProfile
        print(f"[DEBUG Serializer] validated_data restante: {validated_data}")
        for field, value in validated_data.items():
            print(f"[DEBUG Serializer] Atualizando {field} para: {value}")
            setattr(instance, field, value)
        
        # Atualizar foto se fornecida
        if photo:
            instance.photo = photo
            print(f"[DEBUG Serializer] Foto atualizada: {photo.name}")
        
        # Salvar UserProfile
        instance.save()
        print(f"[DEBUG Serializer] UserProfile salvo")
        
        # Recarregar do banco para garantir
        user.refresh_from_db()
        instance.refresh_from_db()
        
        return instance
