from django.db import models

from core.models import AuditModel, OrganizationScopedModel, SoftDeleteModel


class Trimester(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    STATUS_CHOICES = [('PLANEJADO', 'Planejado'), ('EM_ANDAMENTO', 'Em andamento'), ('ENCERRADO', 'Encerrado')]

    numero = models.PositiveSmallIntegerField()
    ano = models.PositiveIntegerField()
    titulo = models.CharField(max_length=120, blank=True)
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    quantidade_licoes = models.PositiveSmallIntegerField(default=13)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PLANEJADO')

    class Meta:
        ordering = ['-ano', '-numero']
        unique_together = ('organization', 'ano', 'numero')

    def __str__(self):
        return f'{self.numero}º Trimestre {self.ano}'


class Lesson(AuditModel, OrganizationScopedModel, SoftDeleteModel):
    STATUS_CHOICES = [('ABERTA', 'Aberta'), ('FINALIZADA', 'Finalizada')]

    numero = models.PositiveIntegerField()
    tema = models.CharField(max_length=255)
    data = models.DateField()
    revista = models.CharField(max_length=255)
    texto_aureo = models.CharField(max_length=255, blank=True)
    texto_biblico = models.TextField(blank=True)
    objetivo = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ABERTA')
    trimestre = models.PositiveSmallIntegerField()
    ano = models.PositiveIntegerField()

    class Meta:
        ordering = ['-data', 'numero']
        unique_together = ('organization', 'trimestre', 'ano', 'numero')

    def __str__(self):
        return f'Lição {self.numero} - {self.tema}'
