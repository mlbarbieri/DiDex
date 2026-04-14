from flask import Flask, render_template, url_for, flash, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from datetime import datetime
from flask_mail import Mail, Message
import random 
import os
from flask import Flask, render_template, request, redirect, url_for, jsonify # <--- Garanta que jsonify esteja aqui

app = Flask(__name__)
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
        # ... pegue os outros campos se tiver (nome, sobrenome) ...

        # 1. Gera um código de 6 dígitos aleatórios
        codigo = str(random.randint(100000, 999999))

        # 2. Cria o usuário com verificado=False e guarda o código
        novo_usuario = User(
        nome=nome,
        sobrenome=sobrenome,
        username=usuario,
        email=email,
        senha=senha,
        data_nascimento=data_nascimento,  # <--- Aqui!
        codigo_verificacao=codigo,
        verificado=False
    )
        
        db.session.add(novo_usuario)
        db.session.commit()

        # 3. Envia o e-mail com o código
        msg = Message('Código de Verificação - DiDex', recipients=[email])
        
        msg.html = f"""
        <div style="background-color: #f3f4f6; padding: 40px 20px; font-family: Arial, sans-serif; text-align: center;">
            <div style="max-width: 450px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; border: 1px solid #e5e7eb; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                
                <div style="margin-bottom: 30px; text-align: center;">
                    <img src="cid:logo_image" alt="DiDex" style="width: 150px; display: block; margin: 0 auto;">
                </div>

                <div style="border-top: 1px solid #f3f4f6; padding-top: 30px;">
                    <h2 style="color: #111827; font-size: 20px; margin-bottom: 10px; font-weight: bold;">Use o código a seguir para validar seu cadastro</h2>
                    <p style="color: #6b7280; font-size: 15px; margin-bottom: 30px;">
                        Por segurança, nunca compartilhe seus códigos com ninguém.
                    </p>

                    <div style="background-color: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 25px; display: block;">
                        <span style="font-size: 36px; font-weight: 800; letter-spacing: 12px; color: #111827; font-family: monospace;">
                            {codigo}
                        </span>
                    </div>

                    <p style="color: #9ca3af; font-size: 13px; margin-top: 40px;">
                        Precisa de ajuda? <a href="#" style="color: #38bdf8; text-decoration: none; font-weight: 600;">Fale conosco</a>.
                    </p>
                </div>
            </div>
            <p style="color: #9ca3af; font-size: 12px; margin-top: 25px;">
                © 2026 DiDex - Conecte sua essência.
            </p>
        </div>
        """

        # Certifique-se de que a imagem está na pasta static com o nome logo.png
        # Verifique se esse bloco existe logo após o msg.html:
        # Verifique se o nome do arquivo na pasta static é logo.png (tudo minúsculo)
        # Certifique-se de que o arquivo se chama logo.png e está na pasta static
        with app.open_resource("static/logo.png") as fp:
            msg.attach(
                "logo.png", 
                "image/png", 
                fp.read(), 
                headers={'Content-ID': '<logo_image>'}
            )
        
        mail.send(msg)

        return redirect(url_for('verificar_email', email=email))
    return render_template('cadastro.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Tudo aqui dentro tem que estar alinhado com o recuo do IF
        usuario_digitado = request.form.get('email_usuario') # <--- Ajustei para bater com o JavaScript
        senha_digitada = request.form.get('senha')
        
        # Procura o usuário no banco
        usuario = User.query.filter((User.email == usuario_digitado) | (User.username == usuario_digitado)).first()

        # Verifica se a senha bate
        if usuario and usuario.senha == senha_digitada:
            login_user(usuario)
            return jsonify({'status': 'sucesso'})
        else:
            return jsonify({'status': 'erro', 'mensagem': 'Usuário ou senha incorretos'}), 401
    
    # Se for GET, apenas carrega a página
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

if __name__ == '__main__':
    app.run(debug=True)