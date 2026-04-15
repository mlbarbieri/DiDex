from flask import Flask, render_template, url_for, flash, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from datetime import datetime
from flask_mail import Mail, Message
import random 
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify # <--- Garanta que jsonify esteja aqui
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'uma_chave_muito_segura_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'verificacao.didex@gmail.com' # Coloque seu e-mail aqui
app.config['MAIL_PASSWORD'] = 'ubcnhzyotycoqgoq'    # Não é a senha normal!
app.config['MAIL_DEFAULT_SENDER'] = 'verificacao.didex@gmail.com'

mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Tabela de Usuários no Banco de Dados
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)
    sobrenome = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha = db.Column(db.String(60), nullable=False)
    data_nascimento = db.Column(db.String(10), nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    codigo_verificacao = db.Column(db.String(6), nullable=True)
    verificado = db.Column(db.Boolean, default=False)
# Tabela de Posts (Para a rede social depois)
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conteudo = db.Column(db.Text, nullable=False)
    data_criacao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@app.route("/")
@app.route("/home")
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('login')) # Manda direto para a página que já funciona
    todos_os_posts = Post.query.order_by(Post.data_criacao.desc()).all()
    return render_template('home.html', posts=todos_os_posts)

# Adicione o methods=['GET', 'POST'] para ele aceitar o envio do formulário
@app.route("/cadastro", methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        email = request.form.get('email')
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        nome = request.form.get('nome')
        sobrenome = request.form.get('sobrenome')
        data_nascimento = request.form.get('data_nascimento')

        # Criptografia
        senha_cripto = bcrypt.generate_password_hash(senha).decode('utf-8')
        codigo = str(random.randint(100000, 999999))

        try:
            # 1. Primeiro salvamos o usuário (O mais importante)
            novo_usuario = User(
                nome=nome,
                sobrenome=sobrenome,
                username=usuario,
                email=email,
                senha=senha_cripto,
                data_nascimento=data_nascimento,
                codigo_verificacao=codigo,
                verificado=False
            )
            db.session.add(novo_usuario)
            db.session.commit()

            # 2. Tentamos enviar o e-mail, mas se der erro, o site NÃO trava
            try:
                msg = Message('Código de Verificação - DiDex', recipients=[email])
                msg.body = f"Seu código de verificação é: {codigo}"
                # Comentei a parte da logo para evitar erros de caminho no servidor por enquanto
                mail.send(msg)
            except Exception as e_mail:
                print(f"Erro ao enviar e-mail: {e_mail}")
                # O cadastro continua mesmo se o e-mail falhar

            return jsonify({'status': 'sucesso', 'url': url_for('verificar_email', email=email)})

        except Exception as e:
            db.session.rollback() # Cancela se der erro no banco
            print(f"Erro no banco: {e}")
            return jsonify({'status': 'erro', 'mensagem': 'Usuário ou E-mail já existem!'}), 400

    return render_template('cadastro.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_digitado = request.form.get('email_usuario')
        senha_digitada = request.form.get('senha')
        
        usuario = User.query.filter((User.email == usuario_digitado) | (User.username == usuario_digitado)).first()

        # USANDO O BCRYPT PARA COMPARAR A SENHA
        if usuario and bcrypt.check_password_hash(usuario.senha, senha_digitada):
            login_user(usuario)
            return jsonify({'status': 'sucesso'})
        else:
            return jsonify({'status': 'erro', 'mensagem': 'Usuário ou senha incorretos'}), 401
    
    return render_template('login.html')

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route("/postar", methods=['POST'])
@login_required
def postar():
    conteudo_post = request.form.get('conteudo')
    if conteudo_post:
        novo_post = Post(conteudo=conteudo_post, author=current_user)
        db.session.add(novo_post)
        db.session.commit()
    return redirect(url_for('home'))

@app.route("/excluir/<int:post_id>")
@login_required
def excluir_post(post_id):
    post = Post.query.get_or_404(post_id)
    # Segurança: Só o autor do post pode excluir
    if post.author == current_user:
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for('home'))

@app.route("/verificar-email/<email>")
def verificar_email(email):
    # Ela só carrega o HTML, o resto o JavaScript faz
    return render_template('verificar_email.html', email=email)

@app.route('/verificar_email_api', methods=['POST'])
def verificar_email_api():
    codigo_digitado = request.form.get('codigo')
    email = request.form.get('email')
    
    usuario = User.query.filter_by(email=email).first()
    
    if usuario and usuario.codigo_verificacao == codigo_digitado:
        usuario.verificado = True
        db.session.commit()
        return jsonify({'status': 'sucesso'})
    else:
        # Se o código estiver errado, ele avisa o JavaScript sem travar
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
# No final do seu app.py
with app.app_context():
    db.create_all() # Isso cria o arquivo .db e as tabelas se elas não existirem
    print("Banco de dados verificado/criado com sucesso!")

if __name__ == '__main__':
    app.run(debug=True)