from django.db import models

from core.models import AuditModel, OrganizationScopedModel, SoftDeleteModel


class Student(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    SEXO_CHOICES = [('M', 'Masculino'), ('F', 'Feminino')]

    class_group = models.ForeignKey(
        'classrooms.ClassGroup',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
    )
    nome = models.CharField(max_length=255)
    sexo = models.CharField(max_length=1, choices=SEXO_CHOICES)
    data_nascimento = models.DateField()
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome']


class StudentAddress(AuditModel):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='endereco')
    cep = models.CharField(max_length=12, blank=True)
    rua = models.CharField(max_length=255, blank=True)
    numero = models.CharField(max_length=30, blank=True)
    complemento = models.CharField(max_length=255, blank=True)
    bairro = models.CharField(max_length=120, blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    uf = models.CharField(max_length=2, blank=True)


class StudentGuardian(AuditModel):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='responsaveis')
    nome = models.CharField(max_length=255)
    telefone = models.CharField(max_length=30, blank=True)
