TIPO_CAMPO = 'CAMPO'
TIPO_IGREJA = 'IGREJA'

FORMATO_CAMPO = 'CAMPO'
FORMATO_IGREJA_INDIVIDUAL = 'IGREJA_INDIVIDUAL'

TIPO_CHOICES = [
    (TIPO_CAMPO, 'Campo'),
    (TIPO_IGREJA, 'Igreja'),
]

FORMATO_CHOICES = [
    (FORMATO_CAMPO, 'Contrato com múltiplas igrejas'),
    (FORMATO_IGREJA_INDIVIDUAL, 'Contrato de uma igreja só'),
]

# Legado (migração / leitura defensiva)
LEGACY_TIPO_CAMPO = ('SEDE',)
LEGACY_TIPO_IGREJA = ('FILIAL', 'CONGREGACAO')
