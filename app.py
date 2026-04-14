import os
import uuid
import qrcode
import io
import base64
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, g
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, or_
from xhtml2pdf import pisa

from models import db, User, Ficha

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave_secreta_baep_xyz123'
# Garantir caminho absoluto para o SQLite funcionar em servidores (PythonAnywhere)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'baep.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

@app.template_filter('format_date')
def format_date(value, format='%d/%m/%Y'):
    if not value: return ""
    if isinstance(value, datetime):
        return value.strftime(format)
    # Se for string vinda do input type="date" (YYYY-MM-DD cada vez mais comum)
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').strftime(format)
    except:
        return value

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_next_num_sequencial():
    year = datetime.now().year
    last_ficha = Ficha.query.filter(Ficha.num_sequencial.like(f"{year}-%")).order_by(Ficha.id.desc()).first()
    if last_ficha:
        last_num = int(last_ficha.num_sequencial.split('-')[1])
        return f"{year}-{last_num + 1:03d}"
    return f"{year}-001"

def notificar_usuarios_por_role(role, subject, body):
    users = User.query.filter_by(role=role).all()
    for u in users:
        send_notification_email(u.email, subject, body)

def send_notification_email(to_email, subject, body):
    # Função desativada a pedido do usuário - Foco em acesso via QR Code
    print(f"Notificação (E-mail desativado): Para: {to_email} | Assunto: {subject}")

def render_pdf(template_name, **kwargs):
    html = render_template(template_name, datetime=datetime, **kwargs)
    result = io.BytesIO()
    # xhtml2pdf likes a bit more help with paths if images are relative, but for now we'll keep it simple
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Login inválido. Verifique usuário e senha.', 'danger')
    # Gera QR Code do site para exibir na tela de login
    import qrcode
    import io
    import base64
    img = qrcode.make(request.host_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template('login.html', qr_base64=qr_base64)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    search = request.args.get('search', '').strip()
    
    if current_user.role == 'ADMIN':
        query = Ficha.query
    elif current_user.role == 'P2':
        query = Ficha.query.filter(or_(Ficha.entrevistador_id == current_user.id, Ficha.status.in_(['P2', 'SJD', 'SUBCMT', 'CMT', 'FINALIZADO'])))
    elif current_user.role == 'SJD':
        query = Ficha.query.filter(or_(Ficha.entrevistador_id == current_user.id, Ficha.status.in_(['SJD', 'SUBCMT', 'CMT', 'FINALIZADO'])))
    elif current_user.role == 'SUBCMT':
        query = Ficha.query.filter(or_(Ficha.entrevistador_id == current_user.id, Ficha.status.in_(['SUBCMT', 'CMT', 'FINALIZADO'])))
    elif current_user.role == 'CMT':
        query = Ficha.query.filter(or_(Ficha.entrevistador_id == current_user.id, Ficha.status.in_(['CMT', 'FINALIZADO'])))
    else:
        query = Ficha.query.filter_by(entrevistador_id=current_user.id)
    
    if search:
        query = query.filter(or_(
            Ficha.nome_completo.ilike(f'%{search}%'),
            Ficha.re.ilike(f'%{search}%'),
            Ficha.num_sequencial.ilike(f'%{search}%')
        ))
        
    fichas = query.order_by(Ficha.data_criacao.desc()).all()
    
    # Todos os usuários podem realizar entrevistas agora
    entrevistadores = User.query.filter(User.role != 'ADMIN').all()
    return render_template('dashboard.html', fichas=fichas, entrevistadores=entrevistadores, search=search)

@app.route('/p1/gerar', methods=['POST'])
@login_required
def gerar_entrevista():
    if current_user.role != 'ADMIN':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))

    entrevistador_id = request.form.get('entrevistador_id')
    if not entrevistador_id:
        flash('Selecione um entrevistador.', 'warning')
        return redirect(url_for('dashboard'))

    novo_uuid = str(uuid.uuid4())
    num_seq = get_next_num_sequencial()

    ficha = Ficha(
        uuid_link=novo_uuid,
        num_sequencial=num_seq,
        entrevistador_id=entrevistador_id
    )
    db.session.add(ficha)
    db.session.commit()

    link = url_for('preencher_candidato', uuid=novo_uuid, _external=True)
    img = qrcode.make(link)
    buf = io.BytesIO()
    img.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    flash('Entrevista gerada com sucesso!', 'success')
    return render_template('sucesso_p1.html', qr_code=qr_b64, link=link, num_seq=num_seq)

@app.route('/formulario/<uuid>', methods=['GET', 'POST'])
def preencher_candidato(uuid):
    ficha = Ficha.query.filter_by(uuid_link=uuid).first_or_404()
    
    if ficha.status != 'AGUARDANDO_CANDIDATO':
        return render_template('mensagem.html', msg="Este formulário já foi respondido ou está em análise.")

    if request.method == 'POST':
        # Dados Pessoais
        ficha.nome_completo = request.form.get('nome_completo')
        ficha.posto_grad = request.form.get('posto_grad')
        ficha.re = request.form.get('re')
        ficha.data_nasc = request.form.get('data_nasc')
        ficha.opm = request.form.get('opm')
        ficha.cpf = request.form.get('cpf')
        ficha.rg = request.form.get('rg')
        ficha.data_ingresso = request.form.get('data_ingresso')
        ficha.tempo_servico = request.form.get('tempo_servico')
        ficha.tempo_averbado = request.form.get('tempo_averbado')
        ficha.endereco = request.form.get('endereco')
        ficha.bairro = request.form.get('bairro')
        ficha.municipio = request.form.get('municipio')
        ficha.celular = request.form.get('celular')
        ficha.email = request.form.get('email')
        ficha.estado_civil = request.form.get('estado_civil')
        ficha.conjuge_pm = request.form.get('conjuge_pm')
        ficha.art_130 = request.form.get('art_130')
        ficha.possui_filhos = request.form.get('possui_filhos')
        ficha.qtd_filhos = request.form.get('qtd_filhos')
        ficha.idade_filhos = request.form.get('idade_filhos')

        # Disciplina
        ficha.disc_ipm = request.form.get('disc_ipm')
        ficha.disc_pad = request.form.get('disc_pad')
        ficha.disc_punicoes = request.form.get('disc_punicoes')

        # Habilitações
        ficha.hab_armamento = request.form.get('hab_armamento')
        ficha.hab_cnh = request.form.get('hab_cnh')
        ficha.hab_sat = request.form.get('hab_sat')

        # Atividade Profissional
        ficha.prof_funcao_atual = request.form.get('prof_funcao_atual')
        ficha.prof_funcoes_ant = request.form.get('prof_funcoes_ant')
        ficha.prof_tempo_operacional = request.form.get('prof_tempo_operacional')
        ficha.prof_unidades = request.form.get('prof_unidades')

        # Formação
        ficha.form_cursos_op = request.form.get('form_cursos_op')
        ficha.form_artes_marciais = request.form.get('form_artes_marciais')
        ficha.form_outros = request.form.get('form_outros')
        ficha.form_forcas_armadas = request.form.get('form_forcas_armadas')
        ficha.form_expertise_adm = request.form.get('form_expertise_adm')

        # EAP
        ficha.eap_saude = request.form.get('eap_saude')
        ficha.eap_taf = request.form.get('eap_taf')
        ficha.eap_tiro = request.form.get('eap_tiro')
        ficha.eap_eap = request.form.get('eap_eap')

        # Foto do Candidato
        foto_b64 = request.form.get('foto_candidato')
        if foto_b64:
            try:
                img_data = base64.b64decode(foto_b64.split(',')[1])
                filename = f"foto_{uuid}.png"
                upload_folder = os.path.join(app.root_path, 'static', 'uploads')
                os.makedirs(upload_folder, exist_ok=True)
                filepath = os.path.join(upload_folder, filename)
                with open(filepath, "wb") as f:
                    f.write(img_data)
                ficha.foto_candidato = filename
            except Exception as e:
                print(f"Erro ao salvar foto: {e}")

        ficha.status = 'ENTREVISTA'
        db.session.commit()
        
        # Enviar email para o entrevistador assignado
        link = url_for('analise', ficha_id=ficha.id, _external=True)
        subj = f"Nova Ficha de Entrevista: {ficha.nome_completo}"
        body = f"O candidato {ficha.nome_completo} preencheu a ficha {ficha.num_sequencial}.\nAguardando seu parecer na plataforma.\n\nAcesse a ficha para analisar: {link}"
        if ficha.entrevistador:
            send_notification_email(ficha.entrevistador.email, subj, body)
            
        return render_template('mensagem.html', msg="Dados enviados com sucesso! Aguarde a convocação para entrevista no 3º BAEP.", type="success")

    return render_template('ficha_candidato.html', ficha=ficha)


@app.route('/analise/<int:ficha_id>', methods=['GET', 'POST'])
@login_required
def analise(ficha_id):
    ficha = Ficha.query.get_or_404(ficha_id)
    
    if request.method == 'POST':
        if current_user.id == ficha.entrevistador_id and ficha.status == 'ENTREVISTA':
            ficha.ent_restricao = request.form.get('ent_restricao')
            ficha.ent_paapm = request.form.get('ent_paapm')
            ficha.ent_limitacao = request.form.get('ent_limitacao')
            ficha.ent_conflitos = request.form.get('ent_conflitos')
            ficha.ent_medida_protetiva = request.form.get('ent_medida_protetiva')
            ficha.ent_bebida = request.form.get('ent_bebida')
            ficha.ent_fumo = request.form.get('ent_fumo')
            ficha.ent_ativ_fisica = request.form.get('ent_ativ_fisica')
            ficha.ent_ciencia = request.form.get('ent_ciencia')
            ficha.ent_ativ_baep = request.form.get('ent_ativ_baep')
            ficha.ent_conhecido = request.form.get('ent_conhecido')
            ficha.ent_motivos = request.form.get('ent_motivos')
            ficha.ent_banco = request.form.get('ent_banco')

            ficha.parecer_entrevista_obs = request.form.get('parecer_entrevista_obs')
            ficha.parecer_entrevista_decisao = request.form.get('parecer_entrevista_decisao')
            ficha.parecer_entrevista_data = datetime.utcnow()
            ficha.status = 'P2'
            db.session.commit() # commit needed if we want the ID, but it already has an ID. Just to be safe no need to commit here, we just need URL.
            link = url_for('analise', ficha_id=ficha.id, _external=True)
            notificar_usuarios_por_role('P2', f"Ação Pendente (P2): {ficha.nome_completo}", f"A ficha de {ficha.nome_completo} ({ficha.num_sequencial}) está aguardando o seu parecer de P2.\n\nAcesse: {link}")
        
        elif current_user.role == 'P2' and ficha.status == 'P2':
            ficha.parecer_p2_obs = request.form.get('parecer_p2_obs')
            ficha.parecer_p2_decisao = request.form.get('parecer_p2_decisao')
            ficha.parecer_p2_data = datetime.utcnow()
            ficha.status = 'SJD'
            link = url_for('analise', ficha_id=ficha.id, _external=True)
            notificar_usuarios_por_role('SJD', f"Ação Pendente (SJD): {ficha.nome_completo}", f"A ficha de {ficha.nome_completo} ({ficha.num_sequencial}) está aguardando o seu parecer de SJD.\n\nAcesse: {link}")
            
        elif current_user.role == 'SJD' and ficha.status == 'SJD':
            ficha.parecer_sjd_obs = request.form.get('parecer_sjd_obs')
            ficha.parecer_sjd_decisao = request.form.get('parecer_sjd_decisao')
            ficha.parecer_sjd_data = datetime.utcnow()
            ficha.status = 'SUBCMT'
            link = url_for('analise', ficha_id=ficha.id, _external=True)
            notificar_usuarios_por_role('SUBCMT', f"Ação Pendente (SUBCMT): {ficha.nome_completo}", f"A ficha de {ficha.nome_completo} ({ficha.num_sequencial}) está aguardando o seu parecer de SubCmt.\n\nAcesse: {link}")
            
        elif current_user.role == 'SUBCMT' and ficha.status == 'SUBCMT':
            ficha.parecer_subcmt_decisao = request.form.get('parecer_subcmt_decisao')
            ficha.parecer_subcmt_data = datetime.utcnow()
            ficha.status = 'CMT'
            link = url_for('analise', ficha_id=ficha.id, _external=True)
            notificar_usuarios_por_role('CMT', f"Ação Pendente (CMT): {ficha.nome_completo}", f"A ficha de {ficha.nome_completo} ({ficha.num_sequencial}) está aguardando o seu parecer de Comando.\n\nAcesse: {link}")

        elif current_user.role == 'CMT' and ficha.status == 'CMT':
            ficha.parecer_cmt_decisao = request.form.get('parecer_cmt_decisao')
            ficha.parecer_cmt_data = datetime.utcnow()
            ficha.status = 'FINALIZADO'

        db.session.commit()
        flash('Parecer registrado com sucesso!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('analise.html', ficha=ficha)

@app.route('/avocar/<int:ficha_id>', methods=['GET', 'POST'])
@login_required
def avocar(ficha_id):
    if current_user.role != 'ADMIN':
        flash('Acesso negado. Apenas P1 (ADMIN) pode avocar fichas.', 'danger')
        return redirect(url_for('dashboard'))
        
    ficha = Ficha.query.get_or_404(ficha_id)
    entrevistadores = User.query.filter(User.role != 'ADMIN').all()
    
    if request.method == 'POST':
        novo_status = request.form.get('novo_status')
        novo_entrevistador_id = request.form.get('novo_entrevistador_id')
        
        if novo_status:
            ficha.status = novo_status
            
            # Se voltou para AGUARDANDO_CANDIDATO, podemos opcionalmente apagar os dados preenchidos 
            # ou mante-los para o candidato corrigir apenas o que errou (o formulario carrega do DB se mantido, 
            # mas vamos manter para facilitar a correção).
            
        if novo_entrevistador_id:
            ficha.entrevistador_id = novo_entrevistador_id
            
        db.session.commit()
        
        # Recarrega o objeto para garantir que as relações (entrevistador) estejam atualizadas
        db.session.refresh(ficha)

        # Enviar email para notificar do recuo/avanço da ficha
        link = url_for('analise', ficha_id=ficha.id, _external=True)
        
        if ficha.status == 'ENTREVISTA' and ficha.entrevistador:
            subj = f"AÇÃO REQUERIDA: Ficha de Entrevista {ficha.num_sequencial}"
            body = f"A ficha de {ficha.nome_completo or 'Candidato'} foi movida/designada para você.\n\nFase Atual: ENTREVISTA\n\nAcesse para realizar o parecer: {link}"
            send_notification_email(ficha.entrevistador.email, subj, body)
            
        elif ficha.status in ['P2', 'SJD', 'SUBCMT', 'CMT']:
            subj = f"Ficha Avocada ({ficha.status}): {ficha.nome_completo}"
            body = f"A ficha {ficha.num_sequencial} de {ficha.nome_completo} foi avocada pela administração e enviada para o seu nível ({ficha.status}).\n\nAcesse para analisar: {link}"
            notificar_usuarios_por_role(ficha.status, subj, body)

        flash(f'Ficha {ficha.num_sequencial} avocada e atualizada com sucesso!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('avocar_ficha.html', ficha=ficha, entrevistadores=entrevistadores)


@app.route('/usuarios')
@login_required
def listar_usuarios():
    if current_user.role != 'ADMIN':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))
    usuarios = User.query.all()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/novo', methods=['POST'])
@login_required
def novo_usuario():
    if current_user.role != 'ADMIN':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))
        
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    nome = request.form.get('nome')
    role = request.form.get('role')
    
    if User.query.filter_by(username=username).first():
        flash('Nome de usuário já existe.', 'danger')
        return redirect(url_for('listar_usuarios'))
        
    user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        nome=nome,
        role=role
    )
    db.session.add(user)
    db.session.commit()
    flash('Usuário criado com sucesso!', 'success')
    return redirect(url_for('listar_usuarios'))

@app.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    if current_user.role != 'ADMIN':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))
        
    user = User.query.get_or_404(id)
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        # Check if new username conflicts with someone else
        existing_user = User.query.filter_by(username=username).first()
        if existing_user and existing_user.id != user.id:
            flash('Nome de usuário já existe, escolha outro.', 'danger')
            return redirect(url_for('editar_usuario', id=user.id))
            
        user.nome = nome
        user.username = username
        user.email = email
        user.role = role
        
        if password: # only update if provided
            user.password = generate_password_hash(password)
            
        db.session.commit()
        flash('Usuário atualizado com sucesso!', 'success')
        return redirect(url_for('listar_usuarios'))
        
    return render_template('editar_usuario.html', user=user)


@app.route('/usuarios/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_usuario(id):
    if current_user.role != 'ADMIN':
        flash('Acesso negado.', 'danger')
        return redirect(url_for('dashboard'))
        
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Você não pode excluir a si mesmo.', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('Usuário excluído com sucesso.', 'success')
        
    return redirect(url_for('listar_usuarios'))

from flask import send_file

@app.route('/exportar/pdf/<int:ficha_id>')
@login_required
def exportar_pdf(ficha_id):
    ficha = Ficha.query.get_or_404(ficha_id)
    # Buscamos a foto se existir para passar o path absoluto para o pisa
    foto_path = None
    if ficha.foto_candidato:
        foto_path = os.path.join(app.root_path, 'static', 'uploads', ficha.foto_candidato)

    pdf_content = render_pdf('pdf_ficha.html', ficha=ficha, foto_path=foto_path)
    
    if pdf_content:
        return send_file(
            io.BytesIO(pdf_content),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Ficha_{ficha.re}_{ficha.num_sequencial}.pdf"
        )
    flash("Erro ao gerar PDF", "danger")
    return redirect(url_for('dashboard'))

@app.route('/exportar/pdf/todos')
@login_required
def exportar_todos_pdf():
    if current_user.role != 'ADMIN':
        flash("Acesso negado.", "danger")
        return redirect(url_for('dashboard'))
        
    fichas = Ficha.query.filter(Ficha.status != 'AGUARDANDO_CANDIDATO').all()
    
    if not fichas:
        flash("Nenhuma ficha disponível para exportar.", "warning")
        return redirect(url_for('dashboard'))

    html_combined = ""
    for f in fichas:
        foto_path = None
        if f.foto_candidato:
            foto_path = os.path.join(app.root_path, 'static', 'uploads', f.foto_candidato)
        html_combined += render_template('pdf_ficha.html', ficha=f, foto_path=foto_path, datetime=datetime)
        html_combined += '<div style="pdf-next-page: always;"></div>'
        
    pdf_content = render_pdf_raw(html_combined)
    
    if pdf_content:
        return send_file(
            io.BytesIO(pdf_content),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Relatorio_Geral_Fichas_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
    flash("Erro ao gerar PDF combinado", "danger")
    return redirect(url_for('dashboard'))

def render_pdf_raw(html):
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None

from sqlalchemy import text

def init_db():
    with app.app_context():
        db.create_all()
        try:
            db.session.execute(text('ALTER TABLE ficha ADD COLUMN foto_candidato VARCHAR(255)'))
            db.session.commit()
        except:
            db.session.rollback()
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password=generate_password_hash('admin123'), nome='Administrador P1', email='admin@baep.com', role='ADMIN'))
            db.session.add(User(username='entrev', password=generate_password_hash('senha123'), nome='Oficial Silva', email='entrev@baep.com', role='ENTREVISTADOR'))
            db.session.add(User(username='p2', password=generate_password_hash('senha123'), nome='Oficial P2', email='p2@baep.com', role='P2'))
            db.session.add(User(username='sjd', password=generate_password_hash('senha123'), nome='Oficial SJD', email='sjd@baep.com', role='SJD'))
            db.session.add(User(username='subcmt', password=generate_password_hash('senha123'), nome='Subcomandante', email='subcmt@baep.com', role='SUBCMT'))
            db.session.add(User(username='cmt', password=generate_password_hash('senha123'), nome='Comandante', email='cmt@baep.com', role='CMT'))
            db.session.commit()

# Inicializa o banco ao carregar (importante para servidores WSGI)
init_db()

if __name__ == '__main__':
    app.run(debug=True)
