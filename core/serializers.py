from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Student, Lesson, Task, Invoice, FinancialEntry, UserProfile, LessonPlan, LessonPlanAttachment, BillingLog, Subscription
from rest_framework import serializers as drf_serializers


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
    user_profile = serializers.SerializerMethodField()
    partner_teachers = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)
    password_confirm = serializers.CharField(write_only=True, required=False)
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
            "password_confirm",
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
        password_confirm = validated_data.pop('password_confirm', None)
        is_admin = validated_data.pop('is_admin', False)
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
    
    class Meta:
        model = UserProfile
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password', 'password_confirm',
            'cpf_cnpj', 'phone', 'cep', 'address', 'city', 'state',
            'timezone', 'language', 'photo',
            'is_admin', 'user_profile', 'role',
            'subscription_status', 'stripe_customer_id'
        ]
        read_only_fields = ['is_admin', 'user_profile', 'username']
    
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
