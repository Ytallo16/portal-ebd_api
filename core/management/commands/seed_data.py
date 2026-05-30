from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from access_control.constants import ROLE_MODULE_MATRIX
from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup, ClassTeacher
from finance.models import Offering
from lessons.models import Lesson, Trimester
from organizations.constants import FORMATO_CAMPO, FORMATO_IGREJA_INDIVIDUAL, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from publications.models import PublicationControl
from students.models import Student, StudentAddress, StudentGuardian

from .seed_churches_data import CHURCH_EBD_SEEDS, LESSON_TEMPLATES, TRIMESTERS_DATA
from students.services import turma_exige_responsavel


class Command(BaseCommand):
    help = 'Cria dados de seed para desenvolvimento local (incluindo usuários)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default='123456',
            help='Senha padrão aplicada para os usuários seed.',
        )

    @staticmethod
    def _update_fields(instance, data):
        changed = False
        for field, value in data.items():
            if getattr(instance, field) != value:
                setattr(instance, field, value)
                changed = True
        if changed:
            instance.save()

    def _seed_church_ebd(
        self,
        church_org,
        users_by_email,
        classes_data,
        students_data,
        lesson_templates,
        trimesters_data,
        today,
    ):
        classes_by_name = {}
        for turma_data in classes_data:
            teacher = users_by_email.get(turma_data['teacher_email'])
            turma, _ = ClassGroup.objects.get_or_create(
                organization=church_org,
                nome=turma_data['nome'],
                defaults={
                    'faixa_etaria': turma_data['faixa_etaria'],
                    'cor': turma_data['cor'],
                    'ativa': True,
                },
            )
            self._update_fields(
                turma,
                {
                    'faixa_etaria': turma_data['faixa_etaria'],
                    'cor': turma_data['cor'],
                    'ativa': True,
                },
            )
            classes_by_name[turma.nome] = turma
            if teacher:
                ClassTeacher.objects.get_or_create(class_group=turma, user=teacher)

        students_by_name = {}
        for student_data in students_data:
            turma = classes_by_name[student_data['turma']]
            student, _ = Student.objects.get_or_create(
                organization=church_org,
                nome=student_data['nome'],
                defaults={
                    'class_group': turma,
                    'sexo': student_data['sexo'],
                    'data_nascimento': student_data['data_nascimento'],
                    'email': student_data['email'],
                    'telefone': student_data['telefone'],
                    'ativo': True,
                },
            )
            self._update_fields(
                student,
                {
                    'class_group': turma,
                    'sexo': student_data['sexo'],
                    'data_nascimento': student_data['data_nascimento'],
                    'email': student_data['email'],
                    'telefone': student_data['telefone'],
                    'ativo': True,
                },
            )
            students_by_name[student.nome] = student
            StudentAddress.objects.update_or_create(student=student, defaults=student_data['endereco'])
            student.responsaveis.all().delete()
            responsavel = student_data.get('responsavel')
            if responsavel and turma_exige_responsavel(turma.faixa_etaria, turma.nome):
                StudentGuardian.objects.create(
                    student=student,
                    nome=responsavel['nome'],
                    telefone=responsavel['telefone'],
                )

        for trimester_entry in trimesters_data:
            trimester, _ = Trimester.objects.get_or_create(
                organization=church_org,
                ano=trimester_entry['ano'],
                numero=trimester_entry['numero'],
                defaults={
                    'titulo': trimester_entry['titulo'],
                    'data_inicio': trimester_entry['data_inicio'],
                    'data_fim': trimester_entry['data_fim'],
                    'quantidade_licoes': trimester_entry['quantidade_licoes'],
                    'status': trimester_entry['status'],
                },
            )
            self._update_fields(
                trimester,
                {
                    'titulo': trimester_entry['titulo'],
                    'data_inicio': trimester_entry['data_inicio'],
                    'data_fim': trimester_entry['data_fim'],
                    'quantidade_licoes': trimester_entry['quantidade_licoes'],
                    'status': trimester_entry['status'],
                    'is_active': True,
                },
            )

        lessons = []
        for lesson_entry in lesson_templates:
            lesson, _ = Lesson.objects.get_or_create(
                organization=church_org,
                trimestre=1,
                ano=2026,
                numero=lesson_entry['numero'],
                defaults={
                    'tema': lesson_entry['tema'],
                    'data': lesson_entry['data'],
                    'revista': 'Lições Bíblicas',
                    'texto_aureo': lesson_entry['texto_aureo'],
                    'texto_biblico': lesson_entry['texto_biblico'],
                    'objetivo': lesson_entry['objetivo'],
                    'status': lesson_entry['status'],
                },
            )
            self._update_fields(
                lesson,
                {
                    'tema': lesson_entry['tema'],
                    'data': lesson_entry['data'],
                    'revista': 'Lições Bíblicas',
                    'texto_aureo': lesson_entry['texto_aureo'],
                    'texto_biblico': lesson_entry['texto_biblico'],
                    'objetivo': lesson_entry['objetivo'],
                    'status': lesson_entry['status'],
                },
            )
            lessons.append(lesson)

        for idx, lesson in enumerate(lessons):
            for turma in classes_by_name.values():
                offering_value = Decimal('35.00') + Decimal(str((idx + 1) * 5))
                existing_offerings = Offering.objects.filter(
                    organization=church_org,
                    lesson=lesson,
                    class_group=turma,
                ).order_by('id')
                if existing_offerings.exists():
                    offering = existing_offerings.first()
                    self._update_fields(
                        offering,
                        {
                            'data': lesson.data,
                            'valor': offering_value,
                            'is_active': True,
                            'deleted_at': None,
                        },
                    )
                    existing_offerings.exclude(id=offering.id).delete()
                else:
                    Offering.objects.create(
                        organization=church_org,
                        lesson=lesson,
                        class_group=turma,
                        data=lesson.data,
                        valor=offering_value,
                    )

                teacher = turma.teachers.order_by('id').first()
                sheet, _ = AttendanceSheet.objects.get_or_create(
                    lesson=lesson,
                    class_group=turma,
                    defaults={
                        'professor': teacher.user if teacher else None,
                        'visitantes': (idx + 1) % 3,
                        'biblias': 1 + (idx % 2),
                        'revistas': 2 + idx,
                        'oferta_valor': offering_value,
                    },
                )
                self._update_fields(
                    sheet,
                    {
                        'professor': teacher.user if teacher else None,
                        'visitantes': (idx + 1) % 3,
                        'biblias': 1 + (idx % 2),
                        'revistas': 2 + idx,
                        'oferta_valor': offering_value,
                        'finalized_at': timezone.make_aware(datetime.combine(today, datetime.min.time()))
                        if lesson.status == 'FINALIZADA'
                        else None,
                    },
                )

                turma_students = Student.objects.filter(organization=church_org, class_group=turma).order_by('id')
                for pos, student in enumerate(turma_students):
                    AttendanceRecord.objects.update_or_create(
                        attendance_sheet=sheet,
                        student=student,
                        defaults={'presente': (idx + pos) % 2 == 0},
                    )

        paid_students = {s['nome'] for s in students_data[: max(1, len(students_data) // 2)]}
        trimester = (
            Trimester.objects.filter(organization=church_org, status='EM_ANDAMENTO', is_active=True)
            .order_by('-ano', '-numero')
            .first()
        )
        if not trimester:
            trimester = (
                Trimester.objects.filter(organization=church_org, is_active=True)
                .order_by('-ano', '-numero')
                .first()
            )

        if trimester:
            for student in students_by_name.values():
                PublicationControl.objects.update_or_create(
                    organization=church_org,
                    class_group=student.class_group,
                    student=student,
                    trimester=trimester,
                    defaults={
                        'person_type': 'aluno',
                        'person_name': student.nome,
                        'professor': None,
                        'recebeu': True,
                        'pagou': student.nome in paid_students,
                    },
                )

            for turma in classes_by_name.values():
                teacher_rel = turma.teachers.order_by('id').first()
                if not teacher_rel:
                    continue
                PublicationControl.objects.update_or_create(
                    organization=church_org,
                    class_group=turma,
                    professor=teacher_rel.user,
                    trimester=trimester,
                    defaults={
                        'person_type': 'professor',
                        'person_name': teacher_rel.user.nome,
                        'student': None,
                        'recebeu': True,
                        'pagou': True,
                    },
                )

        return len(students_by_name), len(classes_by_name)

    def handle(self, *args, **options):
        password = options['password']
        today = timezone.localdate()

        with transaction.atomic():
            organizations_seed = [
                {
                    'key': 'campo_teresina',
                    'parent_key': None,
                    'nome': 'Campo EBD Teresina',
                    'sigla': 'CET',
                    'tipo': TIPO_CAMPO,
                    'formato': FORMATO_CAMPO,
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Pastor Daniel Nascimento',
                    'membros': 1865,
                    'status': 'ATIVA',
                },
                {
                    'key': 'ad_dirceu',
                    'parent_key': 'campo_teresina',
                    'nome': 'AD Dirceu',
                    'sigla': 'ADD',
                    'tipo': TIPO_IGREJA,
                    'formato': '',
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Pr. Carlos Mendes',
                    'membros': 640,
                    'status': 'ATIVA',
                },
                {
                    'key': 'ad_centro',
                    'parent_key': 'campo_teresina',
                    'nome': 'AD Centro',
                    'sigla': 'ADCEN',
                    'tipo': TIPO_IGREJA,
                    'formato': '',
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Pr. Lucas Andrade',
                    'membros': 520,
                    'status': 'ATIVA',
                },
                {
                    'key': 'congregacao_vila_nova',
                    'parent_key': 'campo_teresina',
                    'nome': 'Congregação Vila Nova',
                    'sigla': 'CVN',
                    'tipo': TIPO_IGREJA,
                    'formato': '',
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Dc. José Ferreira',
                    'membros': 205,
                    'status': 'ATIVA',
                },
                {
                    'key': 'campo_parnaiba',
                    'parent_key': None,
                    'nome': 'Campo EBD Parnaíba',
                    'sigla': 'CEP',
                    'tipo': TIPO_CAMPO,
                    'formato': FORMATO_CAMPO,
                    'cidade': 'Parnaíba',
                    'uf': 'PI',
                    'responsavel': 'Pr. Samuel Alves',
                    'membros': 980,
                    'status': 'ATIVA',
                },
                {
                    'key': 'ad_parnaiba_centro',
                    'parent_key': 'campo_parnaiba',
                    'nome': 'AD Parnaíba Centro',
                    'sigla': 'ADPC',
                    'tipo': TIPO_IGREJA,
                    'formato': '',
                    'cidade': 'Parnaíba',
                    'uf': 'PI',
                    'responsavel': 'Pr. Elias Moura',
                    'membros': 410,
                    'status': 'ATIVA',
                },
                {
                    'key': 'ad_standalone',
                    'parent_key': None,
                    'nome': 'AD Standalone',
                    'sigla': 'ADS',
                    'tipo': TIPO_IGREJA,
                    'formato': FORMATO_IGREJA_INDIVIDUAL,
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Pr. João Individual',
                    'membros': 180,
                    'status': 'ATIVA',
                },
            ]

            organizations_by_key = {}
            for org_seed in organizations_seed:
                organization, _ = Organization.objects.get_or_create(
                    nome=org_seed['nome'],
                    defaults={
                        'sigla': org_seed['sigla'],
                        'tipo': org_seed['tipo'],
                        'formato': org_seed.get('formato', ''),
                        'cidade': org_seed['cidade'],
                        'uf': org_seed['uf'],
                        'responsavel': org_seed['responsavel'],
                        'membros': org_seed['membros'],
                        'status': org_seed['status'],
                    },
                )
                self._update_fields(
                    organization,
                    {
                        'sigla': org_seed['sigla'],
                        'tipo': org_seed['tipo'],
                        'formato': org_seed.get('formato', ''),
                        'cidade': org_seed['cidade'],
                        'uf': org_seed['uf'],
                        'responsavel': org_seed['responsavel'],
                        'membros': org_seed['membros'],
                        'status': org_seed['status'],
                    },
                )
                organizations_by_key[org_seed['key']] = organization

            for org_seed in organizations_seed:
                organization = organizations_by_key[org_seed['key']]
                parent = organizations_by_key.get(org_seed['parent_key']) if org_seed['parent_key'] else None
                if organization.parent_id != (parent.id if parent else None):
                    organization.parent = parent
                    organization.save(update_fields=['parent'])

            campo_org = organizations_by_key['campo_teresina']

            users_data = [
                {
                    'email': 'admin@adebd.com',
                    'nome': 'Pastor Daniel Nascimento',
                    'is_staff': True,
                    'is_superuser': True,
                    'role': 'ADMINISTRADOR',
                    'scope': 'global',
                    'membership_keys': ['campo_teresina'],
                    'role_org_keys': [None],
                },
                {
                    'email': 'admin.campo@adebd.com',
                    'nome': 'Pr. André Costa',
                    'is_staff': True,
                    'is_superuser': False,
                    'role': 'SECRETARIO_CAMPO',
                    'scope': 'campo',
                    'membership_keys': ['campo_teresina', 'ad_dirceu', 'ad_centro', 'congregacao_vila_nova'],
                    'role_org_keys': ['campo_teresina'],
                },
                {
                    'email': 'secretaria@adebd.com',
                    'nome': 'Marta Oliveira',
                    'is_staff': True,
                    'is_superuser': False,
                    'role': 'SECRETARIO_IGREJA',
                    'scope': 'secretaria',
                    'membership_keys': ['ad_dirceu'],
                    'role_org_keys': ['ad_dirceu'],
                },
                {
                    'email': 'prof.adultos@adebd.com',
                    'nome': 'Carlos Mendes',
                    'is_staff': False,
                    'is_superuser': False,
                    'role': 'PROFESSOR',
                    'scope': 'sala',
                    'membership_keys': ['ad_dirceu'],
                    'role_org_keys': ['ad_dirceu'],
                },
                {
                    'email': 'prof.jovens@adebd.com',
                    'nome': 'Ana Paula Lima',
                    'is_staff': False,
                    'is_superuser': False,
                    'role': 'PROFESSOR',
                    'scope': 'sala',
                    'membership_keys': ['ad_dirceu'],
                    'role_org_keys': ['ad_dirceu'],
                },
                {
                    'email': 'secretaria.centro@adebd.com',
                    'nome': 'Rosa Mendes',
                    'is_staff': True,
                    'is_superuser': False,
                    'role': 'SECRETARIO_IGREJA',
                    'scope': 'secretaria',
                    'membership_keys': ['ad_centro'],
                    'role_org_keys': ['ad_centro'],
                },
                {
                    'email': 'secretaria.vilanova@adebd.com',
                    'nome': 'Helena Ferreira',
                    'is_staff': True,
                    'is_superuser': False,
                    'role': 'SECRETARIO_IGREJA',
                    'scope': 'secretaria',
                    'membership_keys': ['congregacao_vila_nova'],
                    'role_org_keys': ['congregacao_vila_nova'],
                },
                {
                    'email': 'secretaria.parnaiba@adebd.com',
                    'nome': 'Cláudia Moura',
                    'is_staff': True,
                    'is_superuser': False,
                    'role': 'SECRETARIO_IGREJA',
                    'scope': 'secretaria',
                    'membership_keys': ['ad_parnaiba_centro'],
                    'role_org_keys': ['ad_parnaiba_centro'],
                },
                {
                    'email': 'secretaria.standalone@adebd.com',
                    'nome': 'Irmã Lúcia Standalone',
                    'is_staff': True,
                    'is_superuser': False,
                    'role': 'SECRETARIO_IGREJA',
                    'scope': 'secretaria',
                    'membership_keys': ['ad_standalone'],
                    'role_org_keys': ['ad_standalone'],
                },
            ]

            users_by_email = {}
            for user_data in users_data:
                user, _ = User.objects.get_or_create(
                    email=user_data['email'],
                    defaults={
                        'nome': user_data['nome'],
                        'is_staff': user_data['is_staff'],
                        'is_superuser': user_data['is_superuser'],
                        'is_active': True,
                    },
                )
                self._update_fields(
                    user,
                    {
                        'nome': user_data['nome'],
                        'is_staff': user_data['is_staff'],
                        'is_superuser': user_data['is_superuser'],
                        'is_active': True,
                    },
                )
                user.set_password(password)
                user.save(update_fields=['password'])
                users_by_email[user.email] = user

                for org_key in user_data['membership_keys']:
                    OrganizationMembership.objects.update_or_create(
                        user=user,
                        organization=organizations_by_key[org_key],
                        defaults={'ativo': True, 'role_scope': user_data['scope']},
                    )

            module_matrix = {
                'usuarios': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': True, 'aprovar': True},
                'organizacoes': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
                'turmas': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
                'alunos': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': True, 'aprovar': True},
                'licoes': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
                'frequencia': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
                'financeiro': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
                'revistas': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
                'dashboard': {'visualizar': True, 'criar': False, 'editar': False, 'excluir': False, 'aprovar': False},
            }

            permissions = {}
            for module, permission_flags in module_matrix.items():
                permission, _ = ModulePermission.objects.get_or_create(modulo=module, defaults=permission_flags)
                self._update_fields(permission, permission_flags)
                permissions[module] = permission

            roles_data = {
                'ADMINISTRADOR': {
                    'descricao': 'Acesso total ao sistema',
                    'modules': ROLE_MODULE_MATRIX['ADMINISTRADOR'],
                },
                'SECRETARIO_CAMPO': {
                    'descricao': 'Gestão completa do campo e igrejas filhas',
                    'modules': ROLE_MODULE_MATRIX['SECRETARIO_CAMPO'],
                },
                'SECRETARIO_IGREJA': {
                    'descricao': 'Gestão completa da igreja local',
                    'modules': ROLE_MODULE_MATRIX['SECRETARIO_IGREJA'],
                },
                'PROFESSOR': {
                    'descricao': 'Frequência, ofertas e acompanhamento da turma',
                    'modules': ROLE_MODULE_MATRIX['PROFESSOR'],
                },
            }

            Role.objects.filter(nome__in=['ADMINISTRADOR_CAMPO', 'SECRETARIA', 'TESOUREIRO']).update(ativo=False)

            roles = {}
            for role_name, role_data in roles_data.items():
                role, _ = Role.objects.get_or_create(
                    nome=role_name,
                    defaults={'descricao': role_data['descricao'], 'ativo': True},
                )
                self._update_fields(role, {'descricao': role_data['descricao'], 'ativo': True})
                roles[role_name] = role
                for module in role_data['modules']:
                    RolePermission.objects.get_or_create(role=role, permission=permissions[module])
                RolePermission.objects.filter(role=role).exclude(
                    permission__modulo__in=role_data['modules']
                ).delete()

            for user_data in users_data:
                user = users_by_email[user_data['email']]
                for role_org_key in user_data['role_org_keys']:
                    organization = organizations_by_key[role_org_key] if role_org_key else None
                    UserRole.objects.update_or_create(
                        user=user,
                        role=roles[user_data['role']],
                        organization=organization,
                        defaults={'ativo': True},
                    )

            seeded_churches = []
            total_alunos = 0
            for church_seed in CHURCH_EBD_SEEDS:
                church_org = organizations_by_key[church_seed['org_key']]
                alunos, turmas = self._seed_church_ebd(
                    church_org,
                    users_by_email,
                    church_seed['classes'],
                    church_seed['students'],
                    LESSON_TEMPLATES,
                    TRIMESTERS_DATA,
                    today,
                )
                total_alunos += alunos
                membros = Student.objects.filter(organization=church_org, is_active=True).count()
                church_org.membros = membros
                church_org.save(update_fields=['membros'])
                seeded_churches.append(f"{church_org.nome} ({alunos} alunos, {turmas} turmas)")

            self.stdout.write(self.style.SUCCESS('Seed concluído com sucesso.'))
            self.stdout.write(self.style.SUCCESS(f'Campo seed: {campo_org.nome}'))
            self.stdout.write(self.style.SUCCESS(f'Total de alunos nas igrejas: {total_alunos}'))
            for linha in seeded_churches:
                self.stdout.write(self.style.SUCCESS(f'  • {linha}'))
            self.stdout.write(self.style.SUCCESS(f'Usuários seed: {len(users_data)} (senha padrão: {password})'))
            self.stdout.write(self.style.SUCCESS('Secretário de campo: admin.campo@adebd.com'))
            self.stdout.write(self.style.SUCCESS('Secretárias de igreja: secretaria@ / secretaria.centro@ / secretaria.vilanova@ / secretaria.parnaiba@ / secretaria.standalone@'))
