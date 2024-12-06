from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session
from supabase import create_client, Client  # Correção aqui
from apimercadopago import gerar_link_pagamento
import hashlib
from datetime import date

# Configuração do Flask
app = Flask(__name__)
app.secret_key = "sua_chave_secreta"
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Supabase Configuração
SUPABASE_URL = "https://wqusqihaukuguamdfgvl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndxdXNxaWhhdWt1Z3VhbWRmZ3ZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzI5ODQ3OTEsImV4cCI6MjA0ODU2MDc5MX0.5v8QUmoanjsUxNAN2jlCzw85z_1FEUVoxK02bfqCGQ4"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)  # Agora a variável 'supabase' está corretamente configurada

# Função de hash de senha
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Rota para a loja (store)
@app.route("/store")
def store():
    if "user" not in session:
        flash("Faça login para acessar a loja!")
        return redirect(url_for("login"))
    
    livros = supabase.table("livros").select("*").execute()  # Buscar todos os livros
    return render_template("store.html", livros=livros.data)

# Adicionar ao carrinho
@app.route("/add_to_cart/<int:livro_id>", methods=["POST"])
def add_to_cart(livro_id):
    if "user" not in session:
        flash("Faça login para adicionar itens ao carrinho!")
        return redirect(url_for("login"))

    # Obter informações do livro
    livro = supabase.table("livros").select("*").eq("id", livro_id).execute().data[0]
    qtd = int(request.form["quantidade"])

    # Adicionar livro ao carrinho na sessão
    if "cart" not in session:
        session["cart"] = []

    cart_item = {
        "id": livro["id"],
        "nome": livro["nome"],
        "preco": livro["preco"],
        "quantidade": qtd,
        "total": livro["preco"] * qtd
    }

    session["cart"].append(cart_item)
    flash(f"{livro['nome']} adicionado ao carrinho!")
    return redirect(url_for("store"))

# Finalizar a compra
# Finalizar a compra
@app.route("/checkout", methods=["POST"])
def checkout():
    if "user" not in session:
        flash("Faça login para finalizar a compra!")
        return redirect(url_for("login"))

    cart_items = session.get("cart", [])
    if not cart_items:
        flash("Seu carrinho está vazio!")
        return redirect(url_for("cart"))
    
    # Obter nome do cliente (usuário logado)
    user_nome = session["nome"]
    
    # Calcular o total da compra
    total = sum(item["total"] for item in cart_items)
    
    # Adicionar a venda ao banco de dados (com status 'pendente' inicialmente)
    venda = {
        "cliente_nome": user_nome,
        "total": total,
        "status": "pendente",  # A venda ainda não está concluída até o pagamento ser confirmado
        "data": date.today().isoformat()
    }
    venda_result = supabase.table("vendas").insert(venda).execute()

    if venda_result.error:
        flash("Erro ao registrar a venda!")
        return redirect(url_for("cart"))

    # Para cada item no carrinho, gerar o link de pagamento
    for item in cart_items:
        dados_produto = {
            "id": item["id"],
            "nome": item["nome"],
            "quantidade": item["quantidade"],
            "preco": item["preco"]
        }

        # Gerar o link de pagamento do Mercado Pago
        link_pagamento = gerar_link_pagamento(dados_produto, user_nome)

        # Adicionar o ID da venda no link de pagamento para rastrear a compra
        return redirect(link_pagamento)

    flash("Erro ao gerar o link de pagamento. Tente novamente.")
    return redirect(url_for("cart"))


# Rota de sucesso da compra
# Rota de sucesso da compra
@app.route("/compracerta/<int:produto_id>")
def compra_certa(produto_id):
    # Registrar a venda como concluída
    cliente_email = session["user"]
    cliente_data = supabase.table("clientes").select("*").eq("email", cliente_email).execute().data[0]
    cliente_id = cliente_data["id"]

    # Obter o livro que foi comprado
    livro = supabase.table("livros").select("*").eq("id", produto_id).execute().data[0]
    
    # Registrar a venda na tabela 'vendas'
    venda_result = supabase.table("vendas").update({"status": "concluída"}).eq("cliente_id", cliente_id).eq("livro_id", livro["id"]).execute()
    
    if venda_result.error:
        flash("Erro ao finalizar a venda!")
        return redirect(url_for("store"))

    flash(f"Compra do produto {livro['nome']} realizada com sucesso!")
    return redirect(url_for("store"))


# Rota de erro da compra
@app.route("/compraerrada")
def compra_errada():
    flash("Houve um erro na sua compra. Tente novamente!")
    return redirect(url_for("cart"))

if __name__ == "__main__":
    app.run(debug=True)
