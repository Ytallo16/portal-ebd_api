"""Turmas e alunos expandidos da AD Dirceu (Teresina — bairros Dirceu, Itararé, Renascença)."""
from datetime import date


def _endereco(cep, rua, numero, bairro, cidade='Teresina'):
    return {'cep': cep, 'rua': rua, 'numero': numero, 'bairro': bairro, 'cidade': cidade, 'uf': 'PI'}


DIRCEU_CLASSES = [
    {'nome': 'Berçário', 'faixa_etaria': '0-2 anos', 'cor': '#EC4899', 'teacher_email': 'secretaria@adebd.com'},
    {'nome': 'Jardim de Infância', 'faixa_etaria': '3-5 anos', 'cor': '#F97316', 'teacher_email': 'secretaria@adebd.com'},
    {'nome': 'Primários', 'faixa_etaria': '6-8 anos', 'cor': '#EAB308', 'teacher_email': 'prof.primarios@adebd.com'},
    {'nome': 'Juniores', 'faixa_etaria': '9-11 anos', 'cor': '#22C55E', 'teacher_email': 'prof.primarios@adebd.com'},
    {'nome': 'Adolescentes', 'faixa_etaria': '12-17 anos', 'cor': '#06B6D4', 'teacher_email': 'prof.adolescentes@adebd.com'},
    {'nome': 'Jovens', 'faixa_etaria': '18-25 anos', 'cor': '#0C7A43', 'teacher_email': 'prof.jovens@adebd.com'},
    {'nome': 'Adultos I', 'faixa_etaria': '26-35 anos', 'cor': '#125A94', 'teacher_email': 'prof.adultos@adebd.com'},
    {'nome': 'Adultos II', 'faixa_etaria': '36-50 anos', 'cor': '#068CC3', 'teacher_email': 'prof.adultos2@adebd.com'},
    {'nome': 'Adultos III', 'faixa_etaria': '51+ anos', 'cor': '#0D9488', 'teacher_email': 'prof.adultos2@adebd.com'},
]

_DIRCEU_RUAS = [
    ('64001-000', 'Rua São Pedro', '123', 'Dirceu I'),
    ('64001-120', 'Rua Projetada A', '45', 'Dirceu I'),
    ('64002-200', 'Rua das Acácias', '78', 'Dirceu II'),
    ('64003-310', 'Av. João XXIII', '1500', 'Dirceu II'),
    ('64010-400', 'Rua Barroso', '33', 'Dirceu II'),
    ('64015-500', 'Rua Artur de Vasconcelos', '189', 'Itararé'),
    ('64016-600', 'Rua Projetada B', '210', 'Itararé'),
    ('64018-220', 'Av. Noé Mendes', '800', 'Renascença'),
    ('64018-301', 'Rua Darcy Viana', '156', 'Renascença'),
    ('64019-110', 'Rua João Cabral', '402', 'São Cristóvão'),
    ('64020-205', 'Rua Almirante Tamandaré', '78', 'Fátima'),
    ('64021-330', 'Av. Maranhão', '950', 'Centro'),
    ('64022-415', 'Rua Desembargador Freitas', '210', 'Ilhotas'),
    ('64023-520', 'Rua São João', '512', 'Parque Piauí'),
    ('64024-625', 'Rua Coelho de Resende', '91', 'Centro'),
    ('64025-430', 'Rua Rui Barbosa', '220', 'Centro'),
    ('64052-200', 'Rua Almirante Gomes', '67', 'Centro'),
    ('64053-120', 'Rua Coelho de Resende', '200', 'Centro'),
    ('64053-310', 'Travessa das Flores', '12', 'Dirceu I'),
    ('64055-100', 'Rua Boa Vista', '305', 'Promorar'),
]

# (nome, sexo, data_nascimento, turma, email_slug, responsavel_opcional)
_DIRCEU_ALUNOS_RAW = [
    # Berçário
    ('Miguel Henrique Souza', 'M', date(2024, 2, 14), 'Berçário', 'miguel.souza', ('Ana Souza', '(86) 98801-0101')),
    ('Helena Vitória Lima', 'F', date(2024, 6, 3), 'Berçário', 'helena.lima', ('Carla Lima', '(86) 98801-0102')),
    ('Arthur Gabriel Costa', 'M', date(2023, 11, 20), 'Berçário', 'arthur.costa', ('Paulo Costa', '(86) 98801-0103')),
    ('Sophia Martins Rocha', 'F', date(2024, 1, 8), 'Berçário', 'sophia.rocha', ('Lucia Rocha', '(86) 98801-0104')),
    ('Benício Alves Pereira', 'M', date(2023, 9, 15), 'Berçário', 'benicio.pereira', ('Sandra Pereira', '(86) 98801-0105')),
    ('Alice Fernandes Dias', 'F', date(2024, 4, 22), 'Berçário', 'alice.dias', ('Marcos Dias', '(86) 98801-0106')),
    ('Theo Barbosa Nunes', 'M', date(2024, 8, 1), 'Berçário', 'theo.nunes', ('Patricia Nunes', '(86) 98801-0107')),
    # Jardim
    ('Pedro Lucas Mendes', 'M', date(2021, 3, 10), 'Jardim de Infância', 'pedro.mendes', ('Solange Mendes', '(86) 98802-0201')),
    ('Laura Beatriz Campos', 'F', date(2020, 7, 25), 'Jardim de Infância', 'laura.campos', ('Renato Campos', '(86) 98802-0202')),
    ('Enzo Gabriel Teixeira', 'M', date(2022, 1, 18), 'Jardim de Infância', 'enzo.teixeira', ('Fernanda Teixeira', '(86) 98802-0203')),
    ('Valentina Moura Silva', 'F', date(2021, 11, 5), 'Jardim de Infância', 'valentina.silva', ('Ricardo Silva', '(86) 98802-0204')),
    ('Davi Lucca Freitas', 'M', date(2020, 5, 30), 'Jardim de Infância', 'davi.freitas', ('Helena Freitas', '(86) 98802-0205')),
    ('Heloísa Carvalho Araújo', 'F', date(2022, 9, 12), 'Jardim de Infância', 'heloisa.araujo', ('Roberto Araújo', '(86) 98802-0206')),
    ('Bernardo Pires Gomes', 'M', date(2021, 12, 2), 'Jardim de Infância', 'bernardo.gomes', ('Francisco Gomes', '(86) 98802-0207')),
    ('Manuela Santos Cruz', 'F', date(2020, 4, 17), 'Jardim de Infância', 'manuela.cruz', ('Rosa Cruz', '(86) 98802-0208')),
    ('Noah Ribeiro Lopes', 'M', date(2022, 6, 28), 'Jardim de Infância', 'noah.lopes', ('José Lopes', '(86) 98802-0209')),
    ('Isadora Nascimento', 'F', date(2021, 8, 9), 'Jardim de Infância', 'isadora.nascimento', ('Vera Nascimento', '(86) 98802-0210')),
    # Primários
    ('Gabriel Santos Pereira', 'M', date(2018, 4, 20), 'Primários', 'gabriel.pereira', ('Sandra Pereira', '(86) 98803-0301')),
    ('Sofia Martins Alves', 'F', date(2017, 8, 3), 'Primários', 'sofia.alves', ('Ricardo Alves', '(86) 98803-0302')),
    ('Rafael Costa Oliveira', 'M', date(2019, 1, 15), 'Primários', 'rafael.oliveira', ('Antônio Oliveira', '(86) 98803-0303')),
    ('Yasmin Ferreira Duarte', 'F', date(2018, 10, 27), 'Primários', 'yasmin.duarte', ('Cláudia Duarte', '(86) 98803-0304')),
    ('Samuel Barbosa Neto', 'M', date(2017, 6, 11), 'Primários', 'samuel.neto', ('Daniel Barbosa', '(86) 98803-0305')),
    ('Lívia Correia Macedo', 'F', date(2019, 3, 8), 'Primários', 'livia.macedo', ('Adriana Macedo', '(86) 98803-0306')),
    ('Henrique Melo Cardoso', 'M', date(2018, 12, 19), 'Primários', 'henrique.cardoso', ('Eduardo Cardoso', '(86) 98803-0307')),
    ('Clara Assis Monteiro', 'F', date(2017, 5, 4), 'Primários', 'clara.monteiro', ('Marta Monteiro', '(86) 98803-0308')),
    ('Nicolas Vieira Braga', 'M', date(2019, 9, 23), 'Primários', 'nicolas.braga', ('Luiz Braga', '(86) 98803-0309')),
    ('Marina Cunha Rios', 'F', date(2018, 2, 1), 'Primários', 'marina.rios', ('Silvia Rios', '(86) 98803-0310')),
    ('Théo Pinheiro Maia', 'M', date(2017, 11, 14), 'Primários', 'theo.maia', ('André Maia', '(86) 98803-0311')),
    ('Lara Bezerra Farias', 'F', date(2019, 7, 6), 'Primários', 'lara.farias', ('Cristina Farias', '(86) 98803-0312')),
  # Juniores
    ('Isabela Fernandes', 'F', date(2014, 9, 14), 'Juniores', 'isabela.fernandes', ('Paulo Fernandes', '(86) 98804-0401')),
    ('Gustavo Henrique Lima', 'M', date(2015, 2, 28), 'Juniores', 'gustavo.lima', ('Eduarda Lima', '(86) 98804-0402')),
    ('Letícia Ramos Borges', 'F', date(2014, 6, 7), 'Juniores', 'leticia.borges', ('Marcos Borges', '(86) 98804-0403')),
    ('Felipe Torres Cavalcante', 'M', date(2015, 11, 19), 'Juniores', 'felipe.cavalcante', ('Ana Cavalcante', '(86) 98804-0404')),
    ('Juliana Paiva Sousa', 'F', date(2014, 3, 22), 'Juniores', 'juliana.sousa', ('Carlos Sousa', '(86) 98804-0405')),
    ('Bruno César Matos', 'M', date(2015, 8, 5), 'Juniores', 'bruno.matos', ('Teresa Matos', '(86) 98804-0406')),
    ('Camila Duarte Rezende', 'F', date(2014, 12, 30), 'Juniores', 'camila.rezende', ('João Rezende', '(86) 98804-0407')),
    ('Eduardo Filho Miranda', 'M', date(2015, 4, 16), 'Juniores', 'eduardo.miranda', ('Lucia Miranda', '(86) 98804-0408')),
    ('Vitória Alencar Pontes', 'F', date(2014, 1, 9), 'Juniores', 'vitoria.pontes', ('Raimundo Pontes', '(86) 98804-0409')),
    ('Igor Santana Bezerra', 'M', date(2015, 10, 3), 'Juniores', 'igor.bezerra', ('Neide Bezerra', '(86) 98804-0410')),
    ('Lorena Gomes Cavalcanti', 'F', date(2014, 7, 21), 'Juniores', 'lorena.cavalcanti', ('Pedro Cavalcanti', '(86) 98804-0411')),
    ('Ryan Souza Magalhães', 'M', date(2015, 5, 13), 'Juniores', 'ryan.magalhaes', ('Eliane Magalhães', '(86) 98804-0412')),
    # Adolescentes
    ('Beatriz Costa', 'F', date(2008, 1, 10), 'Adolescentes', 'beatriz.costa', ('Paulo Costa', '(86) 98777-1234')),
    ('Thiago Henrique Barros', 'M', date(2009, 5, 18), 'Adolescentes', 'thiago.barros', ('Maria Barros', '(86) 98805-0501')),
    ('Amanda Vitória Pires', 'F', date(2010, 3, 2), 'Adolescentes', 'amanda.pires', ('Francisco Pires', '(86) 98805-0502')),
    ('Leonardo Silva Moura', 'M', date(2008, 11, 25), 'Adolescentes', 'leonardo.moura', ('Cláudia Moura', '(86) 98805-0503')),
    ('Júlia Rocha Cavalcante', 'F', date(2009, 8, 14), 'Adolescentes', 'julia.cavalcante', ('Márcio Cavalcante', '(86) 98805-0504')),
    ('Kauã Mendes Freire', 'M', date(2010, 6, 30), 'Adolescentes', 'kaua.freire', ('Solange Freire', '(86) 98805-0505')),
    ('Nicole Almeida Torres', 'F', date(2008, 4, 7), 'Adolescentes', 'nicole.torres', ('Fernando Torres', '(86) 98805-0506')),
    ('Davi Lucas Carneiro', 'M', date(2009, 12, 1), 'Adolescentes', 'davi.carneiro', ('Helena Carneiro', '(86) 98805-0507')),
    ('Yasmim Duarte Lacerda', 'F', date(2010, 2, 20), 'Adolescentes', 'yasmim.lacerda', ('Roberto Lacerda', '(86) 98805-0508')),
    ('Pedro Augusto Nery', 'M', date(2008, 9, 9), 'Adolescentes', 'pedro.nery', ('Vera Nery', '(86) 98805-0509')),
    ('Larissa Vitória Campos', 'F', date(2009, 7, 16), 'Adolescentes', 'larissa.campos', ('Renato Campos', '(86) 98805-0510')),
    ('Erick Fonseca Brandão', 'M', date(2010, 1, 28), 'Adolescentes', 'erick.brandao', ('Sueli Brandão', '(86) 98805-0511')),
    ('Stella Moura Batista', 'F', date(2008, 6, 5), 'Adolescentes', 'stella.batista', ('José Batista', '(86) 98805-0512')),
    # Jovens
    ('João Pedro Silva', 'M', date(1995, 3, 15), 'Jovens', 'joao.silva', None),
    ('Lucas Andrade', 'M', date(2003, 6, 2), 'Jovens', 'lucas.andrade', None),
    ('Gabriela Santos', 'F', date(2002, 4, 12), 'Jovens', 'gabriela.santos', None),
    ('Matheus Oliveira', 'M', date(2001, 9, 28), 'Jovens', 'matheus.oliveira', None),
    ('Isabela Ferreira', 'F', date(2004, 2, 7), 'Jovens', 'isabela.ferreira', None),
    ('Vinícius Ribeiro', 'M', date(2000, 11, 19), 'Jovens', 'vinicius.ribeiro', None),
    ('Larissa Mendes', 'F', date(2003, 7, 3), 'Jovens', 'larissa.mendes', None),
    ('Diego Carvalho', 'M', date(2002, 12, 15), 'Jovens', 'diego.carvalho', None),
    ('Amanda Pires', 'F', date(2004, 5, 22), 'Jovens', 'amanda.pires.jovens', None),
    ('Ricardo Nascimento', 'M', date(2001, 1, 30), 'Jovens', 'ricardo.nascimento', None),
    ('Bianca Alves Cordeiro', 'F', date(2000, 8, 11), 'Jovens', 'bianca.cordeiro', None),
    ('Felipe Augusto Sá', 'M', date(2003, 10, 24), 'Jovens', 'felipe.sa', None),
    ('Natália Gomes Pacheco', 'F', date(2002, 3, 6), 'Jovens', 'natalia.pacheco', None),
    ('Guilherme Costa Rabelo', 'M', date(2001, 6, 17), 'Jovens', 'guilherme.rabelo', None),
    # Adultos I
    ('Mariana Lopes', 'F', date(1998, 11, 8), 'Adultos I', 'mariana.lopes', None),
    ('Carlos Eduardo Lima', 'M', date(1994, 8, 3), 'Adultos I', 'carlos.lima', None),
    ('Fernanda Araújo', 'F', date(1996, 12, 19), 'Adultos I', 'fernanda.araujo', None),
    ('Rodrigo Martins Teles', 'M', date(1993, 4, 25), 'Adultos I', 'rodrigo.teles', None),
    ('Patrícia Helena Dias', 'F', date(1997, 7, 2), 'Adultos I', 'patricia.dias', None),
    ('Anderson Souza Cavalcante', 'M', date(1995, 1, 14), 'Adultos I', 'anderson.cavalcante', None),
    ('Renata Barbosa Figueiredo', 'F', date(1999, 9, 30), 'Adultos I', 'renata.figueiredo', None),
    ('Marcelo Pinto Guimarães', 'M', date(1992, 11, 8), 'Adultos I', 'marcelo.guimaraes', None),
    ('Aline Correia Macedo', 'F', date(1996, 3, 21), 'Adultos I', 'aline.macedo', None),
    ('Fábio Nery Montenegro', 'M', date(1994, 6, 5), 'Adultos I', 'fabio.montenegro', None),
    ('Simone Rocha Valente', 'F', date(1998, 2, 18), 'Adultos I', 'simone.valente', None),
    ('Leandro Assis Portela', 'M', date(1993, 10, 12), 'Adultos I', 'leandro.portela', None),
    ('Cíntia Melo Cardoso', 'F', date(1997, 5, 27), 'Adultos I', 'cintia.cardoso', None),
    ('Hugo Vieira Braga', 'M', date(1995, 8, 9), 'Adultos I', 'hugo.braga', None),
    # Adultos II
    ('José Ferreira', 'M', date(1985, 3, 20), 'Adultos II', 'jose.ferreira', None),
    ('Marta Oliveira Duarte', 'F', date(1988, 7, 11), 'Adultos II', 'marta.duarte', None),
    ('Francisco Lima Neto', 'M', date(1982, 12, 1), 'Adultos II', 'francisco.neto', None),
    ('Benedita Carvalho', 'F', date(1987, 4, 16), 'Adultos II', 'benedita.carvalho', None),
    ('Antônio Pereira Souza', 'M', date(1980, 9, 8), 'Adultos II', 'antonio.souza', None),
    ('Rosa Mendes Silva', 'F', date(1986, 1, 25), 'Adultos II', 'rosa.silva', None),
    ('Paulo Henrique Lima', 'M', date(1983, 6, 3), 'Adultos II', 'paulo.lima', None),
    ('Maria Eduarda Costa', 'F', date(1989, 11, 19), 'Adultos II', 'maria.costa', None),
    ('Samuel Barbosa', 'M', date(1981, 2, 14), 'Adultos II', 'samuel.barbosa', None),
    ('Eliane Magalhães Rios', 'F', date(1984, 8, 30), 'Adultos II', 'eliane.rios', None),
    ('Daniel Nascimento', 'M', date(1987, 5, 7), 'Adultos II', 'daniel.nascimento', None),
    ('Priscila Rocha Alves', 'F', date(1990, 10, 22), 'Adultos II', 'priscila.alves', None),
    ('Marcos Santos Oliveira', 'M', date(1982, 7, 18), 'Adultos II', 'marcos.oliveira', None),
    # Adultos III
    ('Benedita Carvalho Silva', 'F', date(1968, 5, 12), 'Adultos III', 'benedita.silva', None),
    ('Francisco Lima', 'M', date(1965, 11, 3), 'Adultos III', 'francisco.lima', None),
    ('Sebastião Alves Mendes', 'M', date(1970, 2, 28), 'Adultos III', 'sebastiao.mendes', None),
    ('Terezinha Gomes Rocha', 'F', date(1962, 8, 15), 'Adultos III', 'terezinha.rocha', None),
    ('João Batista Pereira', 'M', date(1958, 4, 9), 'Adultos III', 'joao.pereira', None),
    ('Maria das Graças Souza', 'F', date(1960, 12, 24), 'Adultos III', 'maria.gracas', None),
    ('Antônio José Nunes', 'M', date(1967, 7, 6), 'Adultos III', 'antonio.nunes', None),
    ('Raimunda Nonata Dias', 'F', date(1963, 1, 31), 'Adultos III', 'raimunda.dias', None),
    ('Pedro Henrique Lima', 'M', date(1975, 5, 3), 'Adultos III', 'pedro.lima', None),
    ('Lucélia Fontes Aragão', 'F', date(1955, 9, 20), 'Adultos III', 'lucelia.aragao', None),
]


def build_dirceu_students():
    students = []
    for idx, (nome, sexo, nasc, turma, slug, responsavel) in enumerate(_DIRCEU_ALUNOS_RAW):
        cep, rua, numero, bairro = _DIRCEU_RUAS[idx % len(_DIRCEU_RUAS)]
        telefone = f'(86) 99{idx % 100:02d}-{9000 + idx:04d}'
        entry = {
            'nome': nome,
            'sexo': sexo,
            'data_nascimento': nasc,
            'email': f'{slug}.dirceu@email.com',
            'telefone': telefone,
            'turma': turma,
            'endereco': _endereco(cep, rua, numero, bairro),
        }
        if responsavel:
            entry['responsavel'] = {'nome': responsavel[0], 'telefone': responsavel[1]}
        students.append(entry)
    return students


DIRCEU_EBD_SEED = {
    'org_key': 'ad_dirceu',
    'classes': DIRCEU_CLASSES,
    'students': build_dirceu_students(),
}
