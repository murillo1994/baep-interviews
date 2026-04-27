from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import pytz
from datetime import datetime

def get_now_br():
    return datetime.now(pytz.timezone('America/Sao_Paulo')).replace(tzinfo=None)

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(200), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # Roles: ADMIN (P1), ENTREVISTADOR, AUXILIAR_P2, P2, AUXILIAR_SJD, SJD, SUBCMT, CMT

class Ficha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid_link = db.Column(db.String(100), unique=True, nullable=False)
    num_sequencial = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(50), default='AGUARDANDO_CANDIDATO') # AGUARDANDO_CANDIDATO, ENTREVISTA, P2, SJD, SUBCMT, CMT, FINALIZADO
    data_criacao = db.Column(db.DateTime, default=get_now_br)
    
    entrevistador_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    entrevistador = db.relationship('User', foreign_keys=[entrevistador_id])

    # --- 1) Dados Pessoais ---
    nome_completo = db.Column(db.String(150))
    posto_grad = db.Column(db.String(50))
    re = db.Column(db.String(20))
    data_nasc = db.Column(db.String(20))
    opm = db.Column(db.String(100))
    cpf = db.Column(db.String(20))
    rg = db.Column(db.String(20))
    data_ingresso = db.Column(db.String(20))
    tempo_servico = db.Column(db.String(50))
    tempo_averbado = db.Column(db.String(50))
    endereco = db.Column(db.String(200))
    bairro = db.Column(db.String(100))
    municipio = db.Column(db.String(100))
    celular = db.Column(db.String(20))
    email = db.Column(db.String(100))
    estado_civil = db.Column(db.String(50))
    conjuge_pm = db.Column(db.String(10))
    art_130 = db.Column(db.String(10))
    possui_filhos = db.Column(db.String(10))
    qtd_filhos = db.Column(db.String(10))
    idade_filhos = db.Column(db.String(100))

    # --- 2) Disciplina ---
    disc_ipm = db.Column(db.Text)
    disc_pad = db.Column(db.Text)
    disc_punicoes = db.Column(db.Text)

    # --- 3) Habilitações ---
    hab_armamento = db.Column(db.Text)
    hab_cnh = db.Column(db.String(50))
    hab_sat = db.Column(db.String(50))

    # --- 4) Atividade Profissional ---
    prof_funcao_atual = db.Column(db.String(150))
    prof_funcoes_ant = db.Column(db.Text)
    prof_tempo_operacional = db.Column(db.Text)
    prof_unidades = db.Column(db.Text)

    # --- 5) Formação e Cursos ---
    form_cursos_op = db.Column(db.Text)
    form_artes_marciais = db.Column(db.Text)
    form_outros = db.Column(db.Text)
    form_forcas_armadas = db.Column(db.Text)
    form_expertise_adm = db.Column(db.Text)

    # --- 6) EAP / Inspeção Anual ---
    eap_saude = db.Column(db.String(100))
    eap_taf = db.Column(db.String(100))
    eap_tiro = db.Column(db.String(100))
    eap_eap = db.Column(db.String(100))

    # --- 6.5) Foto ---
    foto_candidato = db.Column(db.String(255))

    # --- 7) Entrevista ---
    ent_restricao = db.Column(db.String(10)) # Sim / Não
    ent_restricao_quais = db.Column(db.Text)
    ent_restricao_vezes = db.Column(db.String(50))
    ent_restricao_motivo = db.Column(db.Text)
    ent_restricao_tempo = db.Column(db.String(100))
    
    ent_paapm = db.Column(db.String(10)) # Sim / Não
    ent_paapm_motivo = db.Column(db.Text)
    ent_paapm_restricao = db.Column(db.String(100))
    
    ent_limitacao = db.Column(db.Text)
    ent_conflitos = db.Column(db.Text)
    ent_medida_protetiva = db.Column(db.Text)
    
    ent_bebida = db.Column(db.String(10)) # Sim / Não
    ent_bebida_freq = db.Column(db.String(100))
    
    ent_fumo = db.Column(db.String(10)) # Sim / Não
    ent_ativ_fisica = db.Column(db.Text)
    ent_ciencia = db.Column(db.String(20))
    ent_ativ_baep = db.Column(db.Text)
    ent_conhecido = db.Column(db.Text)
    ent_motivos = db.Column(db.Text)
    ent_banco = db.Column(db.String(100))

    # --- 8) Pareceres ---
    parecer_entrevista_obs = db.Column(db.Text)
    parecer_entrevista_decisao = db.Column(db.String(20)) # Favorável / Desfavorável
    parecer_entrevista_data = db.Column(db.DateTime)

    parecer_p2_obs = db.Column(db.Text)
    parecer_p2_decisao = db.Column(db.String(20))
    parecer_p2_data = db.Column(db.DateTime)

    parecer_sjd_obs = db.Column(db.Text)
    parecer_sjd_decisao = db.Column(db.String(20))
    parecer_sjd_data = db.Column(db.DateTime)

    parecer_subcmt_decisao = db.Column(db.String(20))
    parecer_subcmt_data = db.Column(db.DateTime)

    parecer_cmt_decisao = db.Column(db.String(50)) # Ofício / Arquivo / Não é interesse
    parecer_cmt_data = db.Column(db.DateTime)

class Movimentacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ficha_id = db.Column(db.Integer, db.ForeignKey('ficha.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status_anterior = db.Column(db.String(50))
    status_novo = db.Column(db.String(50))
    data = db.Column(db.DateTime, default=get_now_br)
    descricao = db.Column(db.Text)
    
    user = db.relationship('User')
    ficha = db.relationship('Ficha', backref=db.backref('movimentacoes', lazy=True, order_by='Movimentacao.data.desc()', cascade="all, delete-orphan"))
