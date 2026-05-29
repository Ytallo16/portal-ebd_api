from datetime import date, timedelta

from rest_framework import status
from rest_framework.test import APITestCase

from access_control.models import ModulePermission, Role, RolePermission, UserRole
from accounts.models import User
from classrooms.models import ClassGroup, ClassTeacher
from lessons.models import Lesson
from organizations.constants import FORMATO_CAMPO, TIPO_CAMPO, TIPO_IGREJA
from organizations.models import Organization, OrganizationMembership
from students.models import Student


class AttendanceFlowTests(APITestCase):
    def setUp(self):
        self.campo = Organization.objects.create(
            nome='Campo Presença',
            sigla='CP',
            tipo=TIPO_CAMPO,
            formato=FORMATO_CAMPO,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.org = Organization.objects.create(
            nome='Org Presença',
            sigla='OP',
            tipo=TIPO_IGREJA,
            parent=self.campo,
            cidade='Teresina',
            uf='PI',
            status='ATIVA',
        )
        self.user = User.objects.create_user(email='coord@test.com', password='123456', nome='Coordenador')
        OrganizationMembership.objects.create(user=self.user, organization=self.org, ativo=True)

        role = Role.objects.create(nome='ADMINISTRADOR')
        for module in ['licoes', 'frequencia', 'turmas', 'alunos']:
            perm = ModulePermission.objects.create(
                modulo=module,
                visualizar=True,
                criar=True,
                editar=True,
                excluir=True,
                aprovar=True,
            )
            RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user, role=role, organization=self.org, ativo=True)

        login = self.client.post('/api/v1/auth/login', {'email': 'coord@test.com', 'password': '123456'}, format='json')
        token = login.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}', HTTP_X_ORGANIZATION_ID=str(self.org.id))

        self.class_group = ClassGroup.objects.create(
            organization=self.org,
            nome='Adultos I',
            faixa_etaria='26-35',
            cor='#125A94',
            created_by=self.user,
        )
        self.lesson = Lesson.objects.create(
            organization=self.org,
            numero=1,
            tema='Tema',
            data=date.today(),
            revista='Revista',
            trimestre=1,
            ano=2026,
            created_by=self.user,
        )
        self.student = Student.objects.create(
            organization=self.org,
            class_group=self.class_group,
            nome='Aluno 1',
            sexo='M',
            data_nascimento=date(2000, 1, 1),
            created_by=self.user,
        )

    def test_full_attendance_and_finalize_lesson_flow(self):
        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': self.class_group.id,
                'professor': self.user.id,
                'visitantes': 1,
                'biblias': 10,
                'revistas': 8,
                'oferta_valor': '25.00',
            },
            format='json',
        )
        self.assertEqual(create_sheet.status_code, status.HTTP_201_CREATED)
        sheet_id = create_sheet.data['id']

        records = self.client.post(
            f'/api/v1/attendance-sheets/{sheet_id}/records/',
            {'records': [{'student': self.student.id, 'presente': True}]},
            format='json',
        )
        self.assertEqual(records.status_code, status.HTTP_200_OK)
        self.assertEqual(len(records.data['records']), 1)
        self.assertTrue(records.data['records'][0]['presente'])

        finalize_lesson = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(finalize_lesson.status_code, status.HTTP_200_OK)
        self.assertEqual(finalize_lesson.data['status'], 'FINALIZADA')

    def test_finalize_lesson_without_sheet_fails(self):
        response = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('turmas_pendentes', response.data)

    def test_finalize_lesson_requires_all_active_classes(self):
        ClassGroup.objects.create(
            organization=self.org,
            nome='Jovens',
            faixa_etaria='18-25',
            cor='#0C7A43',
            created_by=self.user,
        )

        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': self.class_group.id,
                'professor': self.user.id,
                'visitantes': 0,
                'biblias': 0,
                'revistas': 0,
                'oferta_valor': '0.00',
            },
            format='json',
        )
        sheet_id = create_sheet.data['id']
        self.client.post(
            f'/api/v1/attendance-sheets/{sheet_id}/records/',
            {'records': [{'student': self.student.id, 'presente': True}]},
            format='json',
        )

        response = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Jovens', response.data['turmas_pendentes'])

    def test_professor_cannot_finalize_lesson(self):
        professor = User.objects.create_user(
            email='prof@test.com',
            password='123456',
            nome='Professor',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role, _ = Role.objects.get_or_create(
            nome='PROFESSOR',
            defaults={'descricao': 'Professor', 'ativo': True},
        )
        for module in ['licoes', 'frequencia', 'turmas', 'alunos']:
            perm, _ = ModulePermission.objects.get_or_create(
                modulo=module,
                defaults={
                    'visualizar': True,
                    'criar': True,
                    'editar': True,
                    'excluir': False,
                    'aprovar': False,
                },
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)
        UserRole.objects.create(user=professor, role=role, organization=self.org, ativo=True)
        ClassTeacher.objects.create(class_group=self.class_group, user=professor)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'prof@test.com', 'password': '123456'},
            format='json',
        )
        token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': self.class_group.id,
                'professor': professor.id,
                'visitantes': 0,
                'biblias': 0,
                'revistas': 0,
                'oferta_valor': '0.00',
            },
            format='json',
        )
        self.assertEqual(create_sheet.status_code, status.HTTP_201_CREATED)
        sheet_id = create_sheet.data['id']
        self.client.post(
            f'/api/v1/attendance-sheets/{sheet_id}/records/',
            {'records': [{'student': self.student.id, 'presente': True}]},
            format='json',
        )

        response = self.client.post(f'/api/v1/lessons/{self.lesson.id}/finalize/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_professor_can_update_ebd_totals_on_lesson_day(self):
        professor = User.objects.create_user(
            email='prof2@test.com',
            password='123456',
            nome='Professor 2',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role, _ = Role.objects.get_or_create(
            nome='PROFESSOR',
            defaults={'descricao': 'Professor', 'ativo': True},
        )
        for module in ['licoes', 'frequencia', 'turmas', 'alunos', 'financeiro']:
            perm, _ = ModulePermission.objects.get_or_create(
                modulo=module,
                defaults={
                    'visualizar': True,
                    'criar': True,
                    'editar': True,
                    'excluir': False,
                    'aprovar': False,
                },
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)
        UserRole.objects.create(user=professor, role=role, organization=self.org, ativo=True)
        ClassTeacher.objects.create(class_group=self.class_group, user=professor)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'prof2@test.com', 'password': '123456'},
            format='json',
        )
        token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': self.lesson.id,
                'class_group': self.class_group.id,
                'professor': professor.id,
                'visitantes': 1,
                'biblias': 2,
                'revistas': 3,
                'oferta_valor': '10.00',
            },
            format='json',
        )
        self.assertEqual(create_sheet.status_code, status.HTTP_201_CREATED)
        sheet_id = create_sheet.data['id']

        patch = self.client.patch(
            f'/api/v1/attendance-sheets/{sheet_id}/',
            {
                'visitantes': 4,
                'biblias': 5,
                'revistas': 6,
                'oferta_valor': '42.50',
            },
            format='json',
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(patch.data['biblias'], 5)
        self.assertEqual(patch.data['revistas'], 6)
        self.assertEqual(str(patch.data['oferta_valor']), '42.50')

        from finance.models import Offering

        offering = Offering.objects.get(
            lesson_id=self.lesson.id,
            class_group_id=self.class_group.id,
            organization=self.org,
            is_active=True,
        )
        self.assertEqual(str(offering.valor), '42.50')

    def test_professor_can_register_on_past_lesson_date(self):
        past_lesson = Lesson.objects.create(
            organization=self.org,
            numero=99,
            tema='Lição passada',
            data=date.today() - timedelta(days=21),
            revista='Revista',
            trimestre=1,
            ano=2026,
            status='ABERTA',
            created_by=self.user,
        )
        professor = User.objects.create_user(
            email='prof3@test.com',
            password='123456',
            nome='Professor 3',
        )
        OrganizationMembership.objects.create(
            user=professor,
            organization=self.org,
            ativo=True,
        )
        role, _ = Role.objects.get_or_create(
            nome='PROFESSOR',
            defaults={'descricao': 'Professor', 'ativo': True},
        )
        for module in ['licoes', 'frequencia', 'turmas', 'alunos']:
            perm, _ = ModulePermission.objects.get_or_create(
                modulo=module,
                defaults={
                    'visualizar': True,
                    'criar': True,
                    'editar': True,
                    'excluir': False,
                    'aprovar': False,
                },
            )
            RolePermission.objects.get_or_create(role=role, permission=perm)
        UserRole.objects.create(user=professor, role=role, organization=self.org, ativo=True)
        ClassTeacher.objects.create(class_group=self.class_group, user=professor)

        login = self.client.post(
            '/api/v1/auth/login',
            {'email': 'prof3@test.com', 'password': '123456'},
            format='json',
        )
        token = login.data['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token}',
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )

        create_sheet = self.client.post(
            '/api/v1/attendance-sheets/',
            {
                'lesson': past_lesson.id,
                'class_group': self.class_group.id,
                'professor': professor.id,
                'visitantes': 2,
                'biblias': 3,
                'revistas': 4,
                'oferta_valor': '15.00',
            },
            format='json',
        )
        self.assertEqual(create_sheet.status_code, status.HTTP_201_CREATED)
