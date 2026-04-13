from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from attendance.models import AttendanceRecord, AttendanceSheet
from classrooms.models import ClassGroup, ClassTeacher
from finance.models import Offering
from lessons.models import Lesson, Trimester
from organizations.models import Organization, OrganizationMembership
from publications.models import PublicationControl
from students.models import Student, StudentAddress, StudentGuardian


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

    def handle(self, *args, **options):
        password = options['password']
        today = timezone.localdate()

        with transaction.atomic():
            organizations_seed = [
                {
                    'key': 'campo_teresina',
                    'nome': 'Campo EBD Teresina',
                    'sigla': 'CET',
                    'tipo': 'SEDE',
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Pastor Daniel Nascimento',
                    'membros': 1865,
                    'status': 'ATIVA',
                },
                {
                    'key': 'ad_dirceu',
                    'nome': 'AD Dirceu',
                    'sigla': 'ADD',
                    'tipo': 'FILIAL',
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Pr. Carlos Mendes',
                    'membros': 640,
                    'status': 'ATIVA',
                },
                {
                    'key': 'ad_centro',
                    'nome': 'AD Centro',
                    'sigla': 'ADCEN',
                    'tipo': 'FILIAL',
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Pr. Lucas Andrade',
                    'membros': 520,
                    'status': 'ATIVA',
                },
                {
                    'key': 'congregacao_vila_nova',
                    'nome': 'Congregação Vila Nova',
                    'sigla': 'CVN',
                    'tipo': 'CONGREGACAO',
                    'cidade': 'Teresina',
                    'uf': 'PI',
                    'responsavel': 'Dc. José Ferreira',
                    'membros': 205,
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
                        'cidade': org_seed['cidade'],
                        'uf': org_seed['uf'],
                        'responsavel': org_seed['responsavel'],
                        'membros': org_seed['membros'],
                        'status': org_seed['status'],
                    },
                )
                organizations_by_key[org_seed['key']] = organization

            campo_org = organizations_by_key['campo_teresina']
            org = organizations_by_key['ad_dirceu']

            users_data = [
                {
                    'email': 'admin@adebd.com',
                    'nome': 'Pastor Daniel Nascimento',
                    'is_staff': True,
                    'is_superuser': True,
                    'role': 'ADMINISTRADOR',
                    'scope': 'global',
                    'membership_keys': ['ad_dirceu'],
                    'role_org_keys': ['ad_dirceu'],
                },
                {
                    'email': 'admin.campo@adebd.com',
                    'nome': 'Pr. André Costa',
                    'is_staff': True,
                    'is_superuser': False,
                    'role': 'ADMINISTRADOR_CAMPO',
                    'scope': 'campo',
                    'membership_keys': ['campo_teresina', 'ad_dirceu', 'ad_centro', 'congregacao_vila_nova'],
                    'role_org_keys': ['campo_teresina', 'ad_dirceu', 'ad_centro', 'congregacao_vila_nova'],
                },
                {
                    'email': 'secretaria@adebd.com',
                    'nome': 'Marta Oliveira',
                    'is_staff': True,
                    'is_superuser': False,
                    'role': 'SECRETARIA',
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
                    'email': 'tesouraria@adebd.com',
                    'nome': 'Roberto Sousa',
                    'is_staff': False,
                    'is_superuser': False,
                    'role': 'TESOUREIRO',
                    'scope': 'financeiro',
                    'membership_keys': ['ad_dirceu'],
                    'role_org_keys': ['ad_dirceu'],
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
                'alunos': {'visualizar': True, 'criar': True, 'editar': True, 'excluir': False, 'aprovar': True},
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
                    'modules': list(module_matrix.keys()),
                },
                'ADMINISTRADOR_CAMPO': {
                    'descricao': 'Administração do campo e de múltiplas igrejas',
                    'modules': list(module_matrix.keys()),
                },
                'SECRETARIA': {
                    'descricao': 'Gestão de turmas, alunos, lições e publicações',
                    'modules': ['dashboard', 'turmas', 'alunos', 'licoes', 'frequencia', 'revistas'],
                },
                'PROFESSOR': {
                    'descricao': 'Lançamentos de presença e consulta de lições',
                    'modules': ['dashboard', 'alunos', 'licoes', 'frequencia', 'revistas'],
                },
                'TESOUREIRO': {
                    'descricao': 'Gestão de ofertas e visão de painel',
                    'modules': ['dashboard', 'financeiro'],
                },
            }

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

            for user_data in users_data:
                user = users_by_email[user_data['email']]
                for role_org_key in user_data['role_org_keys']:
                    UserRole.objects.update_or_create(
                        user=user,
                        role=roles[user_data['role']],
                        organization=organizations_by_key[role_org_key],
                        defaults={'ativo': True},
                    )

            class_data = [
                {
                    'nome': 'Adultos I',
                    'faixa_etaria': '26-35 anos',
                    'cor': '#125A94',
                    'teacher_email': 'prof.adultos@adebd.com',
                },
                {
                    'nome': 'Jovens',
                    'faixa_etaria': '18-25 anos',
                    'cor': '#0C7A43',
                    'teacher_email': 'prof.jovens@adebd.com',
                },
                {
                    'nome': 'Adolescentes',
                    'faixa_etaria': '13-17 anos',
                    'cor': '#A76A00',
                    'teacher_email': 'secretaria@adebd.com',
                },
            ]

            classes_by_name = {}
            for turma_data in class_data:
                turma, _ = ClassGroup.objects.get_or_create(
                    organization=org,
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
                ClassTeacher.objects.get_or_create(
                    class_group=turma,
                    user=users_by_email[turma_data['teacher_email']],
                )

            students_data = [
                {
                    'nome': 'João Pedro Silva',
                    'sexo': 'M',
                    'data_nascimento': date(1995, 3, 15),
                    'email': 'joao@email.com',
                    'telefone': '(86) 99901-1234',
                    'turma': 'Adultos I',
                    'endereco': {
                        'cep': '64001-000',
                        'rua': 'Rua São Pedro',
                        'numero': '123',
                        'bairro': 'Dirceu I',
                        'cidade': 'Teresina',
                        'uf': 'PI',
                    },
                    'responsavel': {'nome': 'Maria da Silva', 'telefone': '(86) 98811-1122'},
                },
                {
                    'nome': 'Lucas Andrade',
                    'sexo': 'M',
                    'data_nascimento': date(2003, 6, 2),
                    'email': 'lucas.andrade@email.com',
                    'telefone': '(86) 99922-5678',
                    'turma': 'Jovens',
                    'endereco': {
                        'cep': '64018-220',
                        'rua': 'Av. Noé Mendes',
                        'numero': '800',
                        'bairro': 'Renascença',
                        'cidade': 'Teresina',
                        'uf': 'PI',
                    },
                    'responsavel': {'nome': 'Edna Andrade', 'telefone': '(86) 98999-4455'},
                },
                {
                    'nome': 'Beatriz Costa',
                    'sexo': 'F',
                    'data_nascimento': date(2008, 1, 10),
                    'email': 'beatriz.costa@email.com',
                    'telefone': '(86) 99933-9876',
                    'turma': 'Adolescentes',
                    'endereco': {
                        'cep': '64025-430',
                        'rua': 'Rua Projetada',
                        'numero': '45',
                        'bairro': 'Itararé',
                        'cidade': 'Teresina',
                        'uf': 'PI',
                    },
                    'responsavel': {'nome': 'Paulo Costa', 'telefone': '(86) 98777-1234'},
                },
                {
                    'nome': 'Mariana Lopes',
                    'sexo': 'F',
                    'data_nascimento': date(1998, 11, 8),
                    'email': 'mariana.lopes@email.com',
                    'telefone': '(86) 99844-7878',
                    'turma': 'Adultos I',
                    'endereco': {
                        'cep': '64053-120',
                        'rua': 'Rua Coelho de Resende',
                        'numero': '91',
                        'bairro': 'Centro',
                        'cidade': 'Teresina',
                        'uf': 'PI',
                    },
                    'responsavel': {'nome': 'José Lopes', 'telefone': '(86) 99111-0055'},
                },
            ]

            students_by_name = {}
            for student_data in students_data:
                turma = classes_by_name[student_data['turma']]
                student, _ = Student.objects.get_or_create(
                    organization=org,
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
                StudentAddress.objects.update_or_create(
                    student=student,
                    defaults=student_data['endereco'],
                )
                StudentGuardian.objects.update_or_create(
                    student=student,
                    nome=student_data['responsavel']['nome'],
                    defaults={'telefone': student_data['responsavel']['telefone']},
                )

            lesson_data = [
                {
                    'numero': 1,
                    'tema': 'O Início da Jornada de Fé',
                    'data': date(2026, 1, 4),
                    'texto_aureo': 'Hebreus 11:1',
                    'texto_biblico': 'Gênesis 12:1-9',
                    'objetivo': 'Compreender o chamado de Abraão para uma vida de fé.',
                    'status': 'FINALIZADA',
                },
                {
                    'numero': 2,
                    'tema': 'A Obediência que Transforma',
                    'data': date(2026, 1, 11),
                    'texto_aureo': 'Tiago 1:22',
                    'texto_biblico': 'Êxodo 3:1-12',
                    'objetivo': 'Aplicar princípios de obediência bíblica no cotidiano.',
                    'status': 'FINALIZADA',
                },
                {
                    'numero': 3,
                    'tema': 'Serviço com Propósito',
                    'data': date(2026, 1, 18),
                    'texto_aureo': 'Marcos 10:45',
                    'texto_biblico': 'Atos 6:1-7',
                    'objetivo': 'Entender o valor do serviço cristão na igreja local.',
                    'status': 'ABERTA',
                },
                {
                    'numero': 4,
                    'tema': 'Perseverança e Esperança',
                    'data': date(2026, 1, 25),
                    'texto_aureo': 'Romanos 5:3-5',
                    'texto_biblico': 'Hebreus 12:1-3',
                    'objetivo': 'Fortalecer a perseverança da turma diante dos desafios.',
                    'status': 'ABERTA',
                },
            ]

            trimesters_data = [
                {
                    'numero': 1,
                    'ano': 2026,
                    'titulo': '1º Trimestre 2026',
                    'data_inicio': date(2026, 1, 1),
                    'data_fim': date(2026, 3, 31),
                    'quantidade_licoes': 13,
                    'status': 'EM_ANDAMENTO',
                },
                {
                    'numero': 2,
                    'ano': 2026,
                    'titulo': '2º Trimestre 2026',
                    'data_inicio': date(2026, 4, 1),
                    'data_fim': date(2026, 6, 30),
                    'quantidade_licoes': 13,
                    'status': 'PLANEJADO',
                },
            ]

            for trimester_entry in trimesters_data:
                trimester, _ = Trimester.objects.get_or_create(
                    organization=org,
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
            for lesson_entry in lesson_data:
                lesson, _ = Lesson.objects.get_or_create(
                    organization=org,
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
                        organization=org,
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
                            organization=org,
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

                    turma_students = Student.objects.filter(organization=org, class_group=turma).order_by('id')
                    for pos, student in enumerate(turma_students):
                        AttendanceRecord.objects.update_or_create(
                            attendance_sheet=sheet,
                            student=student,
                            defaults={'presente': (idx + pos) % 2 == 0},
                        )

            for student in students_by_name.values():
                PublicationControl.objects.update_or_create(
                    organization=org,
                    class_group=student.class_group,
                    person_type='aluno',
                    person_name=student.nome,
                    defaults={
                        'student': student,
                        'professor': None,
                        'recebeu': True,
                        'pagou': student.nome in {'João Pedro Silva', 'Lucas Andrade'},
                    },
                )

            for turma in classes_by_name.values():
                teacher_rel = turma.teachers.order_by('id').first()
                if not teacher_rel:
                    continue
                PublicationControl.objects.update_or_create(
                    organization=org,
                    class_group=turma,
                    person_type='professor',
                    person_name=teacher_rel.user.nome,
                    defaults={
                        'student': None,
                        'professor': teacher_rel.user,
                        'recebeu': True,
                        'pagou': True,
                    },
                )

            self.stdout.write(self.style.SUCCESS('Seed concluído com sucesso.'))
            self.stdout.write(self.style.SUCCESS(f'Campo seed: {campo_org.nome}'))
            self.stdout.write(self.style.SUCCESS(f'Organização base de operação: {org.nome}'))
            self.stdout.write(self.style.SUCCESS(f'Usuários seed: {len(users_data)} (senha padrão: {password})'))
            self.stdout.write(self.style.SUCCESS('Admin de campo: admin.campo@adebd.com'))
