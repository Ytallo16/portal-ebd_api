from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User
from organizations.constants import FORMATO_IGREJA_INDIVIDUAL, TIPO_IGREJA
from organizations.models import Organization

from activity_logs.models import ActivityLog
from activity_logs.services import describe_activity


def create_organization(nome):
    return Organization.objects.create(
        nome=nome,
        sigla=nome[:5].upper(),
        tipo=TIPO_IGREJA,
        formato=FORMATO_IGREJA_INDIVIDUAL,
        cidade='Teresina',
        uf='PI',
    )


class ActivityDescriptionTests(TestCase):
    def test_describes_common_and_custom_actions(self):
        self.assertEqual(
            describe_activity('PATCH', '/api/v1/students/42/'),
            ('Atualizou aluno', 'Alunos', 'ID 42'),
        )
        self.assertEqual(
            describe_activity('POST', '/api/v1/users/7/reset-password/'),
            ('Redefiniu a senha de usuário', 'Usuários', 'ID 7'),
        )
        self.assertEqual(
            describe_activity(
                'PUT',
                '/api/v1/lessons/4/classes/8/attendance',
            ),
            ('Atualizou registro de frequência', 'Frequência', ''),
        )


class ActivityLogEndpointTests(TestCase):
    def setUp(self):
        self.organization = create_organization('Igreja Central')
        self.other_organization = create_organization('Igreja Norte')
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='secret',
            nome='Administrador',
            is_superuser=True,
            active_organization=self.organization,
        )
        self.regular_user = User.objects.create_user(
            email='user@example.com',
            password='secret',
            nome='Usuário comum',
            active_organization=self.organization,
        )
        self.client = APIClient()

    def test_records_authenticated_write_with_actor_organization_and_result(self):
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            '/api/v1/me',
            {'nome': 'Administrador Atualizado'},
            format='json',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
            HTTP_USER_AGENT='Activity log test',
            REMOTE_ADDR='127.0.0.1',
        )

        self.assertEqual(response.status_code, 200)
        log = ActivityLog.objects.get()
        self.assertEqual(log.organization, self.organization)
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.actor_name, 'Administrador Atualizado')
        self.assertEqual(log.action, 'Editou usuário')
        self.assertEqual(log.event_type, ActivityLog.EVENT_UPDATE)
        self.assertEqual(
            log.changes['nome'],
            {'antes': 'Administrador', 'depois': 'Administrador Atualizado'},
        )
        self.assertEqual(log.status_code, 200)
        self.assertTrue(log.succeeded)
        self.assertEqual(log.ip_address, '127.0.0.1')

    def test_records_successful_login_when_user_has_active_organization(self):
        response = self.client.post(
            '/api/v1/auth/login',
            {'email': self.regular_user.email, 'password': 'secret'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        log = ActivityLog.objects.get()
        self.assertEqual(log.organization, self.organization)
        self.assertEqual(log.actor, self.regular_user)
        self.assertEqual(log.action, 'Iniciou a sessão')

    def test_records_create_update_and_delete_for_business_entity(self):
        self.client.force_authenticate(self.admin)
        headers = {'HTTP_X_ORGANIZATION_ID': str(self.organization.id)}

        created = self.client.post(
            '/api/v1/classes/',
            {
                'nome': 'Jovens',
                'faixa_etaria': '15 a 17 anos',
                'cor': '#123456',
                'ativa': True,
            },
            format='json',
            **headers,
        )
        class_id = created.data['id']
        updated = self.client.patch(
            f'/api/v1/classes/{class_id}/',
            {'nome': 'Jovens e adolescentes'},
            format='json',
            **headers,
        )
        deleted = self.client.delete(
            f'/api/v1/classes/{class_id}/',
            **headers,
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(deleted.status_code, 204)
        events = list(
            ActivityLog.objects.filter(model_label='classrooms.classgroup')
            .order_by('created_at')
            .values_list('event_type', 'action')
        )
        self.assertEqual(
            events,
            [
                ('CREATE', 'Criou turma'),
                ('UPDATE', 'Editou turma'),
                ('DELETE', 'Excluiu turma'),
            ],
        )

    def test_admin_list_is_scoped_to_selected_organization(self):
        ActivityLog.objects.create(
            organization=self.organization,
            actor=self.admin,
            actor_name=self.admin.nome,
            actor_email=self.admin.email,
            action='Criou aluno',
            resource='Alunos',
            method='POST',
            path='/api/v1/students/',
            status_code=201,
            succeeded=True,
        )
        ActivityLog.objects.create(
            organization=self.other_organization,
            actor=self.admin,
            actor_name=self.admin.nome,
            actor_email=self.admin.email,
            action='Criou turma',
            resource='Turmas',
            method='POST',
            path='/api/v1/classes/',
            status_code=201,
            succeeded=True,
        )
        self.client.force_authenticate(self.admin)

        response = self.client.get(
            '/api/v1/activity-logs/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['action'], 'Criou aluno')

    def test_regular_user_cannot_list_activity_logs(self):
        self.client.force_authenticate(self.regular_user)

        response = self.client.get(
            '/api/v1/activity-logs/',
            HTTP_X_ORGANIZATION_ID=str(self.organization.id),
        )

        self.assertEqual(response.status_code, 403)

    def test_active_organization_is_required(self):
        admin_without_context = User.objects.create_user(
            email='admin.no.context@example.com',
            password='secret',
            nome='Admin sem contexto',
            is_superuser=True,
        )
        self.client.force_authenticate(admin_without_context)

        response = self.client.get('/api/v1/activity-logs/')

        self.assertEqual(response.status_code, 400)
