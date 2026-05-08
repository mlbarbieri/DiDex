from flask import Flask, render_template, url_for, flash, redirect, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from datetime import datetime
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import random 
import os
import uuid
import secrets
from PIL import Image

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'uma_chave_muito_segura_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///didex_v2.db'
db = SQLAlchemy(app)

# Configurações de Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'verificacao.didex@gmail.com'
app.config['MAIL_PASSWORD'] = 'ubcnhzyotycoqgoq' 
app.config['MAIL_DEFAULT_SENDER'] = 'verificacao.didex@gmail.com'
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- MODELOS DO BANCO DE DADOS ---

seguidores = db.Table('seguidores',
    db.Column('seguidor_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('seguido_id', db.Integer, db.ForeignKey('user.id'))
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    sobrenome = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(60), nullable=False)
    data_nascimento = db.Column(db.String(10), nullable=False)
    foto_perfil = db.Column(db.String(120), nullable=False, default='default_avatar.png')
    posts = db.relationship('Post', backref='author', lazy=True)
    codigo_verificacao = db.Column(db.String(6), nullable=True)
    verificado = db.Column(db.Boolean, default=False)
    
    seguidos = db.relationship(
        'User', secondary=seguidores,
        primaryjoin=(seguidores.c.seguidor_id == id),
        secondaryjoin=(seguidores.c.seguido_id == id),
        backref=db.backref('seguidores', lazy='dynamic'), lazy='dynamic'
    )

    def esta_seguindo(self, user):
        return self.seguidos.filter(seguidores.c.seguido_id == user.id).count() > 0

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conteudo = db.Column(db.Text, nullable=True)
    imagem = db.Column(db.String(20), nullable=True)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    curtidas = db.relationship('Curtida', backref='post', lazy=True, cascade="all, delete-orphan")
    comentarios = db.relationship('Comentario', backref='post', lazy=True, cascade="all, delete-orphan")

class Curtida(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Comentario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conteudo = db.Column(db.String(200), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    autor = db.relationship('User', backref='meus_comentarios')

class Mensagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    remetente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    lida = db.Column(db.Boolean, default=False)
    remetente = db.relationship('User', foreign_keys=[remetente_id])
    destinatario = db.relationship('User', foreign_keys=[destinatario_id])

# NOVO MODELO DE NOTIFICAÇÃO
class Notificacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    remetente_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tipo = db.Column(db.String(20)) # 'curtida' ou 'seguir'
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    lida = db.Column(db.Boolean, default=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    remetente = db.relationship('User', foreign_keys=[remetente_id])

@app.context_processor
def inject_notifications():
    if current_user.is_authenticated:
        # Conta mensagens não lidas
        msg_count = Mensagem.query.filter_by(destinatario_id=current_user.id, lida=False).count()
        # Conta notificações (curtidas/seguidores) não lidas
        # Importante: Use a variável avisos_count aqui
        notif_count = Notificacao.query.filter_by(user_id=current_user.id, lida=False).count()
        return dict(notificacoes_count=msg_count, avisos_count=notif_count)
    return dict(notificacoes_count=0, avisos_count=0)

# --- FUNÇÕES AUXILIARES ---

def salvar_foto_post(foto_form):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(foto_form.filename)
    nome_arquivo = random_hex + f_ext
    caminho_completo = os.path.join(app.root_path, 'static/posts_pics', nome_arquivo)
    output_size = (800, 800)
    i = Image.open(foto_form)
    i.thumbnail(output_size)
    i.save(caminho_completo)
    return nome_arquivo

# --- ROTAS ---

@app.route("/")
@app.route("/home")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    todos_os_posts = Post.query.order_by(Post.data_criacao.desc()).all()
    return render_template('home.html', posts=todos_os_posts)

@app.route("/postar", methods=['POST'])
@login_required
def postar():
    conteudo = request.form.get('conteudo')
    foto = request.files.get('foto_post')
    nome_foto = None
    if foto and foto.filename != '':
        nome_foto = salvar_foto_post(foto)
    if conteudo or nome_foto:
        novo_post = Post(conteudo=conteudo, author=current_user, imagem=nome_foto)
        db.session.add(novo_post)
        db.session.commit()
    return redirect(url_for('home'))

@app.route("/curtir/<int:post_id>")
@login_required
def curtir(post_id):
    post = Post.query.get_or_404(post_id)
    curtida = Curtida.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if curtida:
        db.session.delete(curtida)
    else:
        nova_curtida = Curtida(user_id=current_user.id, post_id=post_id)
        db.session.add(nova_curtida)
        # Gerar Notificação
        if post.user_id != current_user.id:
            notif = Notificacao(user_id=post.user_id, remetente_id=current_user.id, tipo='curtida', post_id=post.id)
            db.session.add(notif)
    db.session.commit()
    return jsonify({'status': 'sucesso'})

@app.route("/comentar/<int:post_id>", methods=['POST'])
@login_required
def comentar(post_id):
    conteudo = request.form.get('conteudo_comentario')
    if conteudo:
        novo_comentario = Comentario(conteudo=conteudo, user_id=current_user.id, post_id=post_id)
        db.session.add(novo_comentario)
        db.session.commit()
        return jsonify({
            'status': 'sucesso', 
            'usuario': current_user.username, 
            'conteudo': conteudo
        })
    return jsonify({'status': 'erro'}), 400

@app.route("/seguir/<int:user_id>")
@login_required
def seguir(user_id):
    usuario_a_seguir = User.query.get_or_404(user_id)
    if usuario_a_seguir == current_user:
        return jsonify({'status': 'erro'}), 400
    
    if current_user.esta_seguindo(usuario_a_seguir):
        current_user.seguidos.remove(usuario_a_seguir)
        status = 'nao_seguindo'
    else:
        current_user.seguidos.append(usuario_a_seguir)
        status = 'seguindo'
        # Gerar Notificação
        notif = Notificacao(user_id=usuario_a_seguir.id, remetente_id=current_user.id, tipo='seguir')
        db.session.add(notif)
    
    db.session.commit()
    return jsonify({
        'status': status,
        'seguidores_count': usuario_a_seguir.seguidores.count(),
        'seguindo_count': usuario_a_seguir.seguidos.count()
    })

@app.route("/notificacoes")
@login_required
def notificacoes():
    lista = Notificacao.query.filter_by(user_id=current_user.id).order_by(Notificacao.data_criacao.desc()).limit(20).all()
    Notificacao.query.filter_by(user_id=current_user.id, lida=False).update({'lida': True})
    db.session.commit()
    return render_template('notificacoes.html', notificacoes=lista)
    return render_template('notificacoes.html', notificacoes=sua_variavel_aqui)

@app.route("/configuracoes")
@login_required
def configuracoes():
    return render_template('perfil_config.html', usuario=current_user)

@app.route("/upload_foto", methods=['POST'])
@login_required
def upload_foto():
    arquivo = request.files.get('foto')
    if arquivo and arquivo.filename != '':
        extensao = os.path.splitext(arquivo.filename)[1]
        nome_arquivo = f"{current_user.username}_{str(uuid.uuid4())[:8]}{extensao}"
        nome_arquivo = secure_filename(nome_arquivo)
        caminho_salvamento = os.path.join(app.root_path, 'static/profile_pics', nome_arquivo)
        arquivo.save(caminho_salvamento)
        current_user.foto_perfil = nome_arquivo
        db.session.commit()
        flash('Foto de perfil atualizada!', 'sucesso')
    return redirect(url_for('perfil', username=current_user.username))

@app.route("/perfil/<username>")
@login_required
def perfil(username):
    usuario = User.query.filter_by(username=username).first_or_404()
    posts_do_usuario = Post.query.filter_by(author=usuario).order_by(Post.data_criacao.desc()).all()
    return render_template('perfil.html', usuario=usuario, posts=posts_do_usuario)

@app.route("/cadastro", methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        email = request.form.get('email')
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        nome = request.form.get('nome')
        sobrenome = request.form.get('sobrenome')
        data_nascimento = request.form.get('data_nascimento')
        senha_cripto = bcrypt.generate_password_hash(senha).decode('utf-8')
        codigo = str(random.randint(100000, 999999))
        try:
            novo_usuario = User(nome=nome, sobrenome=sobrenome, username=usuario, email=email, 
                               senha=senha_cripto, data_nascimento=data_nascimento, 
                               codigo_verificacao=codigo, verificado=False)
            db.session.add(novo_usuario)
            db.session.commit()
            try:
                msg = Message('Código de Verificação - DiDex', recipients=[email])
                msg.html = f"<h2>Seu código DiDex: {codigo}</h2>"
                mail.send(msg)
            except: pass
            return jsonify({'status': 'sucesso', 'url': url_for('verificar_email', email=email)})
        except:
            db.session.rollback()
            return jsonify({'status': 'erro', 'mensagem': 'Usuário ou e-mail já em uso.'}), 400
    return render_template('cadastro.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('email_usuario')
        p = request.form.get('senha')
        usuario = User.query.filter((User.email == u) | (User.username == u)).first()
        if usuario and bcrypt.check_password_hash(usuario.senha, p):
            login_user(usuario)
            return jsonify({'status': 'sucesso'})
        return jsonify({'status': 'erro'}), 401
    return render_template('login.html')

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/excluir/<int:post_id>")
@login_required
def excluir_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author == current_user:
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('home'))

@app.route("/chat")
@login_required
def chat_lista():
    usuarios = User.query.filter(User.id != current_user.id).all()
    for usuario in usuarios:
        ultima_msg = Mensagem.query.filter(
            ((Mensagem.remetente_id == current_user.id) & (Mensagem.destinatario_id == usuario.id)) |
            ((Mensagem.remetente_id == usuario.id) & (Mensagem.destinatario_id == current_user.id))
        ).order_by(Mensagem.data_envio.desc()).first()
        usuario.ultima_mensagem = ultima_msg
        usuario.n_lidas = Mensagem.query.filter_by(remetente_id=usuario.id, destinatario_id=current_user.id, lida=False).count()
    return render_template("chat_lista.html", usuarios=usuarios)

@app.route("/chat/<int:usuario_id>")
@login_required
def conversa(usuario_id):
    outro_usuario = User.query.get_or_404(usuario_id)
    mensagens = Mensagem.query.filter(
        ((Mensagem.remetente_id == current_user.id) & (Mensagem.destinatario_id == usuario_id)) |
        ((Mensagem.remetente_id == usuario_id) & (Mensagem.destinatario_id == current_user.id))
    ).order_by(Mensagem.data_envio.asc()).all()
    Mensagem.query.filter_by(remetente_id=usuario_id, destinatario_id=current_user.id, lida=False).update({'lida': True})
    db.session.commit()
    return render_template("conversa.html", outro_usuario=outro_usuario, mensagens=mensagens)

@app.route("/enviar_mensagem/<int:usuario_id>", methods=['POST'])
@login_required
def enviar_mensagem(usuario_id):
    conteudo = request.form.get('conteudo')
    if conteudo:
        nova_msg = Mensagem(remetente_id=current_user.id, destinatario_id=usuario_id, conteudo=conteudo)
        db.session.add(nova_msg)
        db.session.commit()
    return redirect(url_for('conversa', usuario_id=usuario_id))

@app.route("/verificar-email/<email>")
def verificar_email(email):
    return render_template('verificar_email.html', email=email)

@app.route('/verificar_email_api', methods=['POST'])
def verificar_email_api():
    c = request.form.get('codigo')
    e = request.form.get('email')
    u = User.query.filter_by(email=e).first()
    if u and u.codigo_verificacao == c:
        u.verificado = True
        db.session.commit()
        return jsonify({'status': 'sucesso'})
    return jsonify({'status': 'erro'}), 400

@app.route('/checar_usuario', methods=['POST'])
def checar_usuario():
    username = request.json.get('username')
    existe = User.query.filter_by(username=username).first() is not None
    return jsonify({'disponivel': not existe})

@app.route('/checar_email', methods=['POST'])
def checar_email():
    email = request.json.get('email')
    existe = User.query.filter_by(email=email).first() is not None
    return jsonify({'disponivel': not existe})

@app.route("/buscar")
@login_required
def buscar():
    query = request.args.get('q')
    resultados = User.query.filter((User.nome.ilike(f'%{query}%')) | (User.username.ilike(f'%{query}%'))).all() if query else []
    return render_template("resultados_busca.html", usuarios=resultados, termo=query)

@app.route("/api/notificacoes")
@login_required
def checar_notificacoes():
    contagem = Mensagem.query.filter_by(destinatario_id=current_user.id, lida=False).count()
    return jsonify({'contagem': contagem})

@app.route("/api/buscar")
@login_required
def api_buscar():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    usuarios = User.query.filter((User.nome.ilike(f'%{query}%')) | (User.username.ilike(f'%{query}%'))).limit(5).all()
    output = []
    for u in usuarios:
        output.append({
            'username': u.username,
            'nome_completo': u.nome,
            'foto': url_for('static', filename='profile_pics/' + u.foto_perfil) if u.foto_perfil else None
        })
    return jsonify(output)

@app.route("/seguidores_lista/<int:user_id>")
@login_required
def seguidores_lista(user_id):
    user = User.query.get_or_404(user_id)
    lista = []
    for u in user.seguidores:
        lista.append({
            'username': u.username,
            'nome': u.nome,
            'foto': url_for('static', filename='profile_pics/' + u.foto_perfil)
        })
    return jsonify(lista)

@app.route("/seguindo_lista/<int:user_id>")
@login_required
def seguindo_lista(user_id):
    user = User.query.get_or_404(user_id)
    lista = []
    for u in user.seguidos:
        lista.append({
            'username': u.username,
            'nome': u.nome,
            'foto': url_for('static', filename='profile_pics/' + u.foto_perfil)
        })
    return jsonify(lista)
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)