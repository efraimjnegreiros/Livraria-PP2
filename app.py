from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_socketio import SocketIO, join_room
from flask_session import Session
from supabase import create_client, Client
import hashlib
from datetime import date
from apimercadopago import gerar_link_pagamento  # Importa a função do arquivo apimercadopago.py

# Configuração do Flask
app = Flask(__name__)
app.secret_key = "sua_chave_secreta"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

SUPABASE_URL = "https://wqusqihaukuguamdfgvl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndxdXNxaWhhdWt1Z3VhbWRmZ3ZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzI5ODQ3OTEsImV4cCI6MjA0ODU2MDc5MX0.5v8QUmoanjsUxNAN2jlCzw85z_1FEUVoxK02bfqCGQ4"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configuração do Socket.IO
socketio = SocketIO(app, cors_allowed_origins="*")

# Função para hash de senha
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Rota de registro (Cadastro de Clientes)
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = hash_password(password)

        # Verificar se o usuário já existe
        existing_user = supabase.table("clientes").select("*").eq("email", email).execute()
        if existing_user.data:
            flash("E-mail já cadastrado!")
            return redirect(url_for("register"))

        # Inserir usuário no banco
        supabase.table("clientes").insert({
            "nome": nome,
            "email": email,
            "senha": hashed_password
        }).execute()

        flash("Cadastro realizado com sucesso!")
        return redirect(url_for("login"))

    return render_template("register.html")

# Rota do Dashboard do Funcionário
@app.route("/funcionario_dashboard")
def funcionario_dashboard():
    # Verificar se o usuário logado é um funcionário
    if "user" not in session:
        flash("Faça login para acessar o painel do funcionário!")
        return redirect(url_for("login"))

    # Verificar se o usuário logado é um funcionário (não um cliente)
    email = session["user"]
    user_funcionario = supabase.table("funcionarios").select("*").eq("email", email).execute()

    if not user_funcionario.data:
        flash("Você não tem permissão para acessar esta página!")
        return redirect(url_for("login"))

    # Se o usuário for funcionário, exibe os links
    return render_template("funcionario_dashboard.html")


# Rota de login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = hash_password(password)

        # Verificar credenciais na tabela de Clientes
        user_cliente = supabase.table("clientes").select("*").eq("email", email).eq("senha", hashed_password).execute()

        # Verificar credenciais na tabela de Funcionarios (vendedor)
        user_funcionario = supabase.table("funcionarios").select("*").eq("email", email).eq("senha", hashed_password).execute()

        if user_cliente.data:
            # Se for cliente, registramos na sessão
            session["user"] = email  # Sessão do cliente
            flash("Login realizado com sucesso!")
            return redirect(url_for("store"))

        elif user_funcionario.data:
            # Se for funcionário (vendedor), registramos na sessão
            session["user"] = email  # Sessão do funcionário
            flash("Login realizado com sucesso!")
            return redirect(url_for("funcionario_dashboard"))

        else:
            flash("E-mail ou senha incorretos!")
            return redirect(url_for("login"))

    return render_template("login.html")


# Rota de logout
@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Você saiu da sua conta!")
    return redirect(url_for("login"))

@app.route("/funcionario")
def funcionario():
    if "user" not in session:
        flash("Faça login para acessar a loja!")
        return redirect(url_for("login"))
    return redirect('127.0.0.1:5000/login')

# Exibir livros
@app.route("/store")
def store():
    if "user" not in session:
        flash("Faça login para acessar a loja!")
        return redirect(url_for("login"))

    # Buscar todos os livros
    livros = supabase.table("livros").select("*").execute()
    return render_template("store.html", livros=livros.data)

# Rota para comprar diretamente
@app.route("/vender/<int:livro_id>", methods=["POST", "GET"])
def vender(livro_id):
    if "user" not in session:
        flash("Faça login para comprar o livro!")
        return redirect(url_for("login"))

    # Obter informações do livro
    livro = supabase.table("livros").select("*").eq("id", livro_id).execute().data[0]

    # Obter nome do cliente da sessão
    cliente_email = session["user"]
    cliente_data = supabase.table("clientes").select("*").eq("email", cliente_email).execute().data[0]
    cliente_nome = cliente_data["nome"]

    # Gerar o link de pagamento usando a API do Mercado Pago
    dados_produto = {
        "id": livro["id"],
        "nome": livro["nome"],
        "quantidade": 1,  # Quantidade de um livro por vez (simples)
        "preco": livro["preco"]
    }
    link_pagamento = gerar_link_pagamento(dados_produto, cliente_nome)

    return render_template("vender.html", livro=livro, link_pagamento=link_pagamento)

@app.route("/compracerta/<int:livro_id>")
def compra_certa(livro_id):
    # Lógica de compra e armazenamento da venda
    # Aqui você pode acessar os parâmetros de consulta (query string) também
    payment_id = request.args.get("payment_id")
    status = request.args.get("status")
    
    # Continue com a lógica da compra, como salvar os dados no banco de dados.
    # Isso pode incluir inserção de registros na tabela de vendas e/ou manipulação do livro
    # com base no livro_id
    livro = supabase.table("livros").select("*").eq("id", livro_id).execute().data[0]
    
    # Registrar a venda
    cliente_email = session.get("user")
    if not cliente_email:
        flash("Por favor, faça login para continuar a compra.")
        return redirect(url_for("login"))
    
    cliente_data = supabase.table("clientes").select("*").eq("email", cliente_email).execute().data[0]
    cliente_id = cliente_data["id"]
    
    venda = {
        "id_livro": livro["id"],
        "qtd": 1,
        "preco": livro["preco"],
        "data_venda": date.today().isoformat(),
    }
    
    venda_result = supabase.table("vendas").insert(venda).execute()
    if not venda_result.data:
        flash("Erro ao finalizar a venda!")
        return redirect(url_for("store"))
    
    flash(f"Compra do produto {livro['nome']} realizada com sucesso!")
    return redirect(url_for("store"))


# Rota de erro da compra
@app.route("/compraerrada")
def compra_errada():
    flash("Houve um erro na sua compra. Tente novamente!")
    return redirect(url_for("store"))

# Iniciar o SocketIO
@socketio.on("connect")
def handle_connect():
    if "user" in session:
        join_room(session["user"])

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
