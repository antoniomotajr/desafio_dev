from flask import Flask, render_template, request, jsonify, send_file, abort, redirect, url_for
import csv
import io
import ipaddress
import math
import os
import secrets
import sqlite3
import tempfile
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path

APP_NAME = "Mota Business Suite"
SOFTWARE_OWNER = "Antonio (Junior) Mota"
SOFTWARE_BUILD_ID = "MBS-2E52A5EAD317D703"
SOFTWARE_FINGERPRINT = "2e52a5ead317d703ab9a7ef9abafd68c5ac99c781f8ddae60b19565b19e10555"
BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "desafio_dev.db"

PORT = int(os.getenv("MOTA_PORT", "5000"))
ALLOW_LAN = os.getenv("MOTA_ALLOW_LAN", "0") == "1"
HOST = "0.0.0.0" if ALLOW_LAN else "127.0.0.1"

# Em modo LAN, exige token. O launcher gera um token por execução.
ACCESS_TOKEN = os.getenv("MOTA_ACCESS_TOKEN", "").strip()
if ALLOW_LAN and not ACCESS_TOKEN:
    ACCESS_TOKEN = secrets.token_urlsafe(24)

MAX_TEXT = 200
MAX_NAME = 120

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB


VENDAS_INICIAIS = [
    ("João Silva", 1200.50), ("João Silva", 950.75),
    ("João Silva", 1800.00), ("João Silva", 1400.30),
    ("João Silva", 1100.90), ("João Silva", 1550.00),
    ("João Silva", 1700.80), ("João Silva", 250.30),
    ("João Silva", 480.75), ("João Silva", 320.40),
    ("Maria Souza", 2100.40), ("Maria Souza", 1350.60),
    ("Maria Souza", 950.20), ("Maria Souza", 1600.75),
    ("Maria Souza", 1750.00), ("Maria Souza", 1450.90),
    ("Maria Souza", 400.50), ("Maria Souza", 180.20),
    ("Maria Souza", 90.75),
    ("Carlos Oliveira", 800.50), ("Carlos Oliveira", 1200.00),
    ("Carlos Oliveira", 1950.30), ("Carlos Oliveira", 1750.80),
    ("Carlos Oliveira", 1300.60), ("Carlos Oliveira", 300.40),
    ("Carlos Oliveira", 500.00), ("Carlos Oliveira", 125.75),
    ("Ana Lima", 1000.00), ("Ana Lima", 1100.50),
    ("Ana Lima", 1250.75), ("Ana Lima", 1400.20),
    ("Ana Lima", 1550.90), ("Ana Lima", 1650.00),
    ("Ana Lima", 75.30), ("Ana Lima", 420.90),
    ("Ana Lima", 315.40),
]

ESTOQUE_INICIAL = [
    (101, "Caneta Azul", 150),
    (102, "Caderno Universitário", 75),
    (103, "Borracha Branca", 200),
    (104, "Lápis Preto HB", 320),
    (105, "Marcador de Texto Amarelo", 90),
]


def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendas(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendedor TEXT NOT NULL,
            valor REAL NOT NULL CHECK(valor >= 0),
            criado_em TEXT NOT NULL,
            codigo_produto INTEGER,
            percentual_comissao REAL,
            FOREIGN KEY(codigo_produto) REFERENCES produtos(codigo)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS produtos(
            codigo INTEGER PRIMARY KEY,
            descricao TEXT NOT NULL,
            estoque INTEGER NOT NULL DEFAULT 0 CHECK(estoque >= 0),
            custo_unitario REAL NOT NULL DEFAULT 0 CHECK(custo_unitario >= 0),
            preco_venda REAL NOT NULL DEFAULT 0 CHECK(preco_venda >= 0),
            comissao_percentual REAL CHECK(
                comissao_percentual IS NULL OR
                (comissao_percentual >= 0 AND comissao_percentual <= 100)
            )
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes(
            id TEXT PRIMARY KEY,
            codigo_produto INTEGER NOT NULL,
            tipo TEXT NOT NULL CHECK(tipo IN ('Entrada','Saída')),
            quantidade INTEGER NOT NULL CHECK(quantidade > 0),
            descricao TEXT,
            estoque_anterior INTEGER NOT NULL,
            estoque_final INTEGER NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY(codigo_produto) REFERENCES produtos(codigo)
        )
    """)

    # Migração segura para bancos criados por versões anteriores.
    venda_cols = {
        row["name"]
        for row in cur.execute("PRAGMA table_info(vendas)").fetchall()
    }
    if "codigo_produto" not in venda_cols:
        cur.execute("ALTER TABLE vendas ADD COLUMN codigo_produto INTEGER")
    if "percentual_comissao" not in venda_cols:
        cur.execute("ALTER TABLE vendas ADD COLUMN percentual_comissao REAL")

    produto_cols = {
        row["name"]
        for row in cur.execute("PRAGMA table_info(produtos)").fetchall()
    }
    if "custo_unitario" not in produto_cols:
        cur.execute(
            "ALTER TABLE produtos ADD COLUMN custo_unitario REAL NOT NULL DEFAULT 0"
        )
    if "preco_venda" not in produto_cols:
        cur.execute(
            "ALTER TABLE produtos ADD COLUMN preco_venda REAL NOT NULL DEFAULT 0"
        )
    if "comissao_percentual" not in produto_cols:
        cur.execute(
            "ALTER TABLE produtos ADD COLUMN comissao_percentual REAL"
        )

    if cur.execute("SELECT COUNT(*) FROM vendas").fetchone()[0] == 0:
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.executemany(
            "INSERT INTO vendas(vendedor,valor,criado_em) VALUES(?,?,?)",
            [(v, x, agora) for v, x in VENDAS_INICIAIS]
        )

    if cur.execute("SELECT COUNT(*) FROM produtos").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO produtos(codigo,descricao,estoque) VALUES(?,?,?)",
            ESTOQUE_INICIAL
        )

    conn.commit()
    conn.close()


def clean_text(value, max_len=MAX_TEXT):
    value = str(value or "").strip()
    if not value:
        return ""
    return value[:max_len]


def safe_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Valor inválido")
    return result


def percentual_padrao(valor):
    """Regra original do desafio, usada como fallback."""
    if valor < 100:
        return 0.0
    if valor < 500:
        return 1.0
    return 5.0


def comissao(valor, percentual=None):
    """
    Se houver percentual personalizado, usa-o.
    Caso contrário, preserva a regra original do desafio.
    """
    pct = percentual_padrao(valor) if percentual is None else percentual
    return valor * (pct / 100.0)


def resolve_comissao(conn, valor, codigo_produto=None, percentual_informado=None):
    """
    Prioridade:
    1. percentual explícito salvo na venda;
    2. percentual cadastrado no produto;
    3. regra original do desafio.
    """
    if percentual_informado is not None:
        pct = safe_float(percentual_informado)
        if pct < 0 or pct > 100:
            raise ValueError("Percentual de comissão deve estar entre 0 e 100.")
        return pct

    if codigo_produto is not None:
        produto = conn.execute(
            "SELECT comissao_percentual FROM produtos WHERE codigo=?",
            (codigo_produto,)
        ).fetchone()

        if produto and produto["comissao_percentual"] is not None:
            return safe_float(produto["comissao_percentual"])

    return percentual_padrao(valor)


def money(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def csv_safe(value):
    """
    Reduz risco de CSV/Formula Injection ao abrir o arquivo no Excel.
    """
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def is_private_or_loopback(addr):
    try:
        ip = ipaddress.ip_address(addr)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


def is_loopback(addr):
    try:
        return ipaddress.ip_address(addr).is_loopback
    except ValueError:
        return False


@app.before_request
def security_gate():
    remote = request.remote_addr or ""

    # Nunca aceita tráfego originado de endereço público.
    if not is_private_or_loopback(remote):
        abort(403)

    # No próprio PC, não exige autenticação.
    if is_loopback(remote):
        return None

    # Fora do PC local, acesso só é permitido quando o modo LAN foi ativado.
    if not ALLOW_LAN:
        abort(403)

    # A tela de login precisa estar acessível antes da autenticação.
    if request.path == "/login":
        return None

    supplied = request.cookies.get("mota_access", "")

    if not ACCESS_TOKEN or not secrets.compare_digest(
        supplied,
        ACCESS_TOKEN
    ):
        # Navegação normal vai para a tela de login.
        if request.method == "GET" and not request.path.startswith("/api/"):
            return redirect(url_for("login"))

        # APIs retornam 401 sem expor o token.
        abort(401)

    # Defesa adicional para operações mutáveis.
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("X-Mota-Request") != "1":
            abort(403)

        origin = request.headers.get("Origin")
        if origin:
            expected = f"{request.scheme}://{request.host}"
            if origin.rstrip("/") != expected.rstrip("/"):
                abort(403)


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'"
    )

    if (
        request.path.startswith("/api/")
        or request.path.startswith("/export/")
        or request.path == "/backup"
        or request.path == "/login"
    ):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"

    return response


def dashboard_data():
    conn = db()
    vendas = conn.execute("""
        SELECT vendedor, valor, percentual_comissao
        FROM vendas
    """).fetchall()
    produtos = conn.execute("SELECT * FROM produtos ORDER BY estoque ASC").fetchall()
    movs = conn.execute("SELECT COUNT(*) FROM movimentacoes").fetchone()[0]
    conn.close()

    resumo = {}
    total = 0.0
    total_com = 0.0

    for row in vendas:
        total += row["valor"]
        c = comissao(row["valor"], row["percentual_comissao"])
        total_com += c
        r = resumo.setdefault(
            row["vendedor"],
            {"qtd": 0, "total": 0.0, "comissao": 0.0}
        )
        r["qtd"] += 1
        r["total"] += row["valor"]
        r["comissao"] += c

    ranking = sorted(
        resumo.items(),
        key=lambda x: x[1]["total"],
        reverse=True
    )

    return {
        "total_vendas": total,
        "total_comissao": total_com,
        "qtd_vendas": len(vendas),
        "total_estoque": sum(x["estoque"] for x in produtos),
        "qtd_produtos": len(produtos),
        "movs": movs,
        "ranking": ranking,
        "alertas": produtos[:5],
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    remote = request.remote_addr or ""

    # No acesso local, login não é necessário.
    if is_loopback(remote):
        return redirect(url_for("index"))

    if not ALLOW_LAN:
        abort(403)

    erro = None

    if request.method == "POST":
        codigo = str(request.form.get("codigo", "")).strip()

        if ACCESS_TOKEN and secrets.compare_digest(
            codigo,
            ACCESS_TOKEN
        ):
            response = redirect(url_for("index"))
            response.set_cookie(
                "mota_access",
                ACCESS_TOKEN,
                httponly=True,
                samesite="Strict",
                secure=False,  # LAN HTTP; use HTTPS em produção.
                max_age=8 * 60 * 60,
                path="/",
            )
            return response

        erro = "Código de acesso inválido."

    return render_template(
        "login.html",
        erro=erro
    )


@app.route("/logout")
def logout():
    response = redirect(url_for("login"))
    response.delete_cookie(
        "mota_access",
        path="/"
    )
    return response


@app.route("/")
def index():
    return render_template(
        "index.html",
        dash=dashboard_data(),
        money=money
    )




@app.route("/api/assinatura-software")
def api_assinatura_software():
    """
    Identificação técnica do build.
    Serve como evidência de autoria e integridade, não como DRM absoluto.
    """
    return jsonify({
        "produto": APP_NAME,
        "titular": SOFTWARE_OWNER,
        "build_id": SOFTWARE_BUILD_ID,
        "fingerprint_sha256": SOFTWARE_FINGERPRINT,
    })


@app.route("/api/readme")
def api_readme():
    """
    Retorna o README do próprio projeto para visualização dentro do sistema.
    Não aceita caminho informado pelo usuário, evitando path traversal.
    """
    readme_path = BASE_DIR / "README.md"

    if not readme_path.is_file():
        return jsonify({
            "ok": False,
            "erro": "README.md não encontrado."
        }), 404

    try:
        content = readme_path.read_text(
            encoding="utf-8",
            errors="replace"
        )
    except OSError:
        return jsonify({
            "ok": False,
            "erro": "Não foi possível ler o README.md."
        }), 500

    # Limite defensivo para nunca devolver arquivo inesperadamente enorme.
    content = content[:200_000]

    return jsonify({
        "ok": True,
        "content": content
    })



@app.route("/api/comissoes-resumo")
def api_comissoes_resumo():
    periodo = request.args.get("periodo", "semana").lower()

    if periodo not in {"semana", "mes", "ano"}:
        return jsonify({
            "ok": False,
            "erro": "Período inválido."
        }), 400

    hoje = date.today()

    if periodo == "semana":
        inicio = hoje - timedelta(days=hoje.weekday())
        fim = inicio + timedelta(days=6)
        titulo_periodo = (
            f"{inicio.strftime('%d/%m/%Y')} a "
            f"{fim.strftime('%d/%m/%Y')}"
        )
    elif periodo == "mes":
        inicio = hoje.replace(day=1)

        if hoje.month == 12:
            proximo = date(hoje.year + 1, 1, 1)
        else:
            proximo = date(hoje.year, hoje.month + 1, 1)

        fim = proximo - timedelta(days=1)
        titulo_periodo = hoje.strftime("%m/%Y")
    else:
        inicio = date(hoje.year, 1, 1)
        fim = date(hoje.year, 12, 31)
        titulo_periodo = str(hoje.year)

    conn = db()

    rows = conn.execute("""
        SELECT
            vendedor,
            valor,
            percentual_comissao,
            criado_em
        FROM vendas
        ORDER BY criado_em ASC
    """).fetchall()

    conn.close()

    resumo = {}

    for row in rows:
        try:
            registro = datetime.strptime(
                row["criado_em"],
                "%Y-%m-%d %H:%M:%S"
            ).date()
        except (TypeError, ValueError):
            continue

        if not (inicio <= registro <= fim):
            continue

        vendedor = row["vendedor"]
        valor = float(row["valor"])
        pct = row["percentual_comissao"]

        com = comissao(valor, pct)

        item = resumo.setdefault(
            vendedor,
            {
                "vendedor": vendedor,
                "vendas": 0,
                "valor_vendido": 0.0,
                "comissao": 0.0,
            }
        )

        item["vendas"] += 1
        item["valor_vendido"] += valor
        item["comissao"] += com

    dados = sorted(
        resumo.values(),
        key=lambda item: item["comissao"],
        reverse=True
    )

    total_vendido = sum(item["valor_vendido"] for item in dados)
    total_comissao = sum(item["comissao"] for item in dados)
    total_vendas = sum(item["vendas"] for item in dados)

    return jsonify({
        "ok": True,
        "periodo": periodo,
        "periodo_label": titulo_periodo,
        "inicio": inicio.strftime("%d/%m/%Y"),
        "fim": fim.strftime("%d/%m/%Y"),
        "total_vendido": total_vendido,
        "total_comissao": total_comissao,
        "total_vendas": total_vendas,
        "lider": dados[0]["vendedor"] if dados else None,
        "dados": dados,
    })


@app.route("/api/vendas")
def api_vendas():
    conn = db()
    rows = conn.execute("""
        SELECT
            v.*,
            p.descricao AS produto
        FROM vendas v
        LEFT JOIN produtos p
          ON p.codigo = v.codigo_produto
        ORDER BY v.id DESC
    """).fetchall()
    conn.close()

    return jsonify([
        {
            "id": r["id"],
            "vendedor": r["vendedor"],
            "valor": r["valor"],
            "codigo_produto": r["codigo_produto"],
            "produto": r["produto"],
            "percentual_comissao": (
                r["percentual_comissao"]
                if r["percentual_comissao"] is not None
                else percentual_padrao(r["valor"])
            ),
            "comissao": comissao(
                r["valor"],
                r["percentual_comissao"]
            ),
            "criado_em": r["criado_em"],
        }
        for r in rows
    ])


@app.route("/api/vendas", methods=["POST"])
def add_venda():
    data = request.get_json(silent=True) or {}

    vendedor = clean_text(data.get("vendedor"), MAX_NAME)

    try:
        valor = safe_float(data.get("valor", 0))
        codigo_produto = data.get("codigo_produto")
        codigo_produto = (
            int(codigo_produto)
            if codigo_produto not in (None, "", 0, "0")
            else None
        )
        pct_data = data.get("percentual_comissao")
        pct_data = (
            safe_float(pct_data)
            if pct_data not in (None, "")
            else None
        )
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

    if not vendedor or valor < 0:
        return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

    conn = db()

    if codigo_produto is not None:
        produto = conn.execute(
            "SELECT codigo FROM produtos WHERE codigo=?",
            (codigo_produto,)
        ).fetchone()
        if not produto:
            conn.close()
            return jsonify({"ok": False, "erro": "Produto não encontrado"}), 400

    try:
        pct = resolve_comissao(
            conn,
            valor,
            codigo_produto,
            pct_data
        )
    except ValueError as exc:
        conn.close()
        return jsonify({"ok": False, "erro": str(exc)}), 400

    conn.execute(
        """
        INSERT INTO vendas(
            vendedor, valor, criado_em,
            codigo_produto, percentual_comissao
        )
        VALUES(?,?,?,?,?)
        """,
        (
            vendedor,
            valor,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            codigo_produto,
            pct,
        )
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/api/vendas/<int:venda_id>", methods=["PUT", "DELETE"])
def edit_venda(venda_id):
    conn = db()

    existing = conn.execute(
        "SELECT id FROM vendas WHERE id=?",
        (venda_id,)
    ).fetchone()

    if not existing:
        conn.close()
        return jsonify({"ok": False, "erro": "Venda não encontrada"}), 404

    if request.method == "DELETE":
        conn.execute(
            "DELETE FROM vendas WHERE id=?",
            (venda_id,)
        )
    else:
        data = request.get_json(silent=True) or {}
        vendedor = clean_text(data.get("vendedor"), MAX_NAME)

        try:
            valor = safe_float(data.get("valor", 0))
            codigo_produto = data.get("codigo_produto")
            codigo_produto = (
                int(codigo_produto)
                if codigo_produto not in (None, "", 0, "0")
                else None
            )
            pct_data = data.get("percentual_comissao")
            pct_data = (
                safe_float(pct_data)
                if pct_data not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

        if not vendedor or valor < 0:
            conn.close()
            return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

        if codigo_produto is not None:
            produto = conn.execute(
                "SELECT codigo FROM produtos WHERE codigo=?",
                (codigo_produto,)
            ).fetchone()
            if not produto:
                conn.close()
                return jsonify({"ok": False, "erro": "Produto não encontrado"}), 400

        try:
            pct = resolve_comissao(
                conn,
                valor,
                codigo_produto,
                pct_data
            )
        except ValueError as exc:
            conn.close()
            return jsonify({"ok": False, "erro": str(exc)}), 400

        conn.execute(
            """
            UPDATE vendas
            SET vendedor=?, valor=?,
                codigo_produto=?, percentual_comissao=?
            WHERE id=?
            """,
            (
                vendedor,
                valor,
                codigo_produto,
                pct,
                venda_id
            )
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/produtos")
def api_produtos():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM produtos ORDER BY codigo"
    ).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


@app.route("/api/produtos", methods=["POST"])
def add_produto():
    data = request.get_json(silent=True) or {}

    try:
        codigo = int(data["codigo"])
        estoque = int(data.get("estoque", 0))
        custo_unitario = safe_float(data.get("custo_unitario", 0))
        preco_venda = safe_float(data.get("preco_venda", 0))

        pct_raw = data.get("comissao_percentual")
        comissao_percentual = (
            safe_float(pct_raw)
            if pct_raw not in (None, "")
            else None
        )
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

    descricao = clean_text(data.get("descricao"))

    if (
        codigo <= 0
        or not descricao
        or estoque < 0
        or custo_unitario < 0
        or preco_venda < 0
        or (
            comissao_percentual is not None
            and not 0 <= comissao_percentual <= 100
        )
    ):
        return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

    conn = db()

    try:
        conn.execute(
            """
            INSERT INTO produtos(
                codigo, descricao, estoque,
                custo_unitario, preco_venda, comissao_percentual
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                codigo,
                descricao,
                estoque,
                custo_unitario,
                preco_venda,
                comissao_percentual
            )
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"ok": False, "erro": "Código já existe"}), 400

    conn.close()
    return jsonify({"ok": True})


@app.route("/api/produtos/<int:codigo>", methods=["PUT", "DELETE"])
def edit_produto(codigo):
    conn = db()

    existing = conn.execute(
        "SELECT codigo FROM produtos WHERE codigo=?",
        (codigo,)
    ).fetchone()

    if not existing:
        conn.close()
        return jsonify({"ok": False, "erro": "Produto não encontrado"}), 404

    if request.method == "DELETE":
        total = conn.execute(
            "SELECT COUNT(*) FROM movimentacoes WHERE codigo_produto=?",
            (codigo,)
        ).fetchone()[0]

        if total:
            conn.close()
            return jsonify({
                "ok": False,
                "erro": "Produto possui movimentações"
            }), 400

        conn.execute(
            "DELETE FROM produtos WHERE codigo=?",
            (codigo,)
        )
    else:
        data = request.get_json(silent=True) or {}
        descricao = clean_text(data.get("descricao"))

        try:
            custo_unitario = safe_float(data.get("custo_unitario", 0))
            preco_venda = safe_float(data.get("preco_venda", 0))
            pct_raw = data.get("comissao_percentual")
            comissao_percentual = (
                safe_float(pct_raw)
                if pct_raw not in (None, "")
                else None
            )
        except (TypeError, ValueError):
            conn.close()
            return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

        if (
            not descricao
            or custo_unitario < 0
            or preco_venda < 0
            or (
                comissao_percentual is not None
                and not 0 <= comissao_percentual <= 100
            )
        ):
            conn.close()
            return jsonify({
                "ok": False,
                "erro": "Dados inválidos"
            }), 400

        conn.execute(
            """
            UPDATE produtos
            SET descricao=?,
                custo_unitario=?,
                preco_venda=?,
                comissao_percentual=?
            WHERE codigo=?
            """,
            (
                descricao,
                custo_unitario,
                preco_venda,
                comissao_percentual,
                codigo
            )
        )

    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/api/movimentacoes")
def api_movs():
    conn = db()
    rows = conn.execute("""
        SELECT
            m.*,
            p.descricao AS produto
        FROM movimentacoes m
        JOIN produtos p
          ON p.codigo=m.codigo_produto
        ORDER BY rowid DESC
    """).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


@app.route("/api/movimentacoes", methods=["POST"])
def add_mov():
    data = request.get_json(silent=True) or {}

    try:
        codigo = int(data["codigo"])
        quantidade = int(data["quantidade"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

    tipo = clean_text(data.get("tipo"), 20)
    descricao = clean_text(data.get("descricao"))

    if quantidade <= 0 or tipo not in ("Entrada", "Saída"):
        return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

    conn = db()

    produto = conn.execute(
        "SELECT * FROM produtos WHERE codigo=?",
        (codigo,)
    ).fetchone()

    if not produto:
        conn.close()
        return jsonify({
            "ok": False,
            "erro": "Produto não encontrado"
        }), 404

    anterior = produto["estoque"]

    if tipo == "Saída":
        if quantidade > anterior:
            conn.close()
            return jsonify({
                "ok": False,
                "erro": "Estoque insuficiente"
            }), 400

        final = anterior - quantidade
    else:
        final = anterior + quantidade

    mov_id = str(uuid.uuid4())
    criado = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE produtos SET estoque=? WHERE codigo=?",
            (final, codigo)
        )
        conn.execute("""
            INSERT INTO movimentacoes(
                id,
                codigo_produto,
                tipo,
                quantidade,
                descricao,
                estoque_anterior,
                estoque_final,
                criado_em
            )
            VALUES(?,?,?,?,?,?,?,?)
        """, (
            mov_id,
            codigo,
            tipo,
            quantidade,
            descricao,
            anterior,
            final,
            criado,
        ))
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    conn.close()

    return jsonify({
        "ok": True,
        "id": mov_id,
        "anterior": anterior,
        "final": final
    })


@app.route("/api/juros", methods=["POST"])
def calc_juros():
    data = request.get_json(silent=True) or {}

    try:
        valor = safe_float(data["valor"])
        venc = datetime.strptime(
            str(data["vencimento"]),
            "%d/%m/%Y"
        ).date()
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Dados inválidos"}), 400

    if valor < 0:
        return jsonify({"ok": False, "erro": "Valor inválido"}), 400

    hoje = date.today()
    dias = max(0, (hoje - venc).days)
    juros = valor * 0.025 * dias

    return jsonify({
        "ok": True,
        "dias": dias,
        "juros": juros,
        "total": valor + juros,
        "status": "EM ATRASO" if dias else "SEM ATRASO",
        "hoje": hoje.strftime("%d/%m/%Y"),
    })


@app.route("/backup")
def backup_db():
    """
    Gera backup consistente via API nativa do SQLite,
    sem enviar diretamente o arquivo em uso.
    """
    source = db()

    with tempfile.NamedTemporaryFile(
        prefix="mota_backup_",
        suffix=".db",
        delete=False
    ) as tmp:
        temp_path = Path(tmp.name)

    try:
        target = sqlite3.connect(temp_path)
        source.backup(target)
        target.close()
        source.close()

        data = temp_path.read_bytes()
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

    nome = (
        "backup_desafio_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".db"
    )

    return send_file(
        io.BytesIO(data),
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=nome,
        max_age=0,
    )


@app.route("/export/vendas.csv")
def export_vendas():
    conn = db()
    rows = conn.execute("""
        SELECT v.*, p.descricao AS produto
        FROM vendas v
        LEFT JOIN produtos p
          ON p.codigo = v.codigo_produto
        ORDER BY v.id
    """).fetchall()
    conn.close()

    output = io.StringIO()
    w = csv.writer(output, delimiter=";")

    w.writerow([
        "ID",
        "Vendedor",
        "Produto",
        "Valor",
        "Percentual de comissão",
        "Comissão",
        "Criado em"
    ])

    for r in rows:
        pct = (
            r["percentual_comissao"]
            if r["percentual_comissao"] is not None
            else percentual_padrao(r["valor"])
        )

        w.writerow([
            r["id"],
            csv_safe(r["vendedor"]),
            csv_safe(r["produto"] or ""),
            f"{r['valor']:.2f}",
            f"{pct:.2f}",
            f"{comissao(r['valor'], pct):.2f}",
            r["criado_em"],
        ])

    mem = io.BytesIO(
        output.getvalue().encode("utf-8-sig")
    )

    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name="vendas.csv",
        max_age=0,
    )


@app.route("/export/estoque.csv")
def export_estoque():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM produtos ORDER BY codigo"
    ).fetchall()
    conn.close()

    output = io.StringIO()
    w = csv.writer(output, delimiter=";")

    w.writerow([
        "Código",
        "Produto",
        "Quantidade",
        "Custo unitário",
        "Preço de venda",
        "Margem bruta estimada",
        "Comissão (%)"
    ])

    for r in rows:
        margem = (
            r["preco_venda"] - r["custo_unitario"]
            if r["preco_venda"] > 0
            else 0
        )

        w.writerow([
            r["codigo"],
            csv_safe(r["descricao"]),
            r["estoque"],
            f"{r['custo_unitario']:.2f}",
            f"{r['preco_venda']:.2f}",
            f"{margem:.2f}",
            (
                ""
                if r["comissao_percentual"] is None
                else f"{r['comissao_percentual']:.2f}"
            ),
        ])

    mem = io.BytesIO(
        output.getvalue().encode("utf-8-sig")
    )

    return send_file(
        mem,
        mimetype="text/csv",
        as_attachment=True,
        download_name="estoque.csv",
        max_age=0,
    )


def print_startup_info():
    print("=" * 62)
    print(f"{APP_NAME} - modo seguro")
    print("=" * 62)
    print(f"Servidor: http://127.0.0.1:{PORT}")

    if ALLOW_LAN:
        print("Modo LAN: ATIVADO")
        print("Acesso de outros dispositivos exige código temporário.")
        print(f"Código de acesso desta execução: {ACCESS_TOKEN}")
        print("O código não é colocado na URL.")
    else:
        print("Modo LAN: DESATIVADO (recomendado)")

    print("=" * 62)


if __name__ == "__main__":
    init_db()
    print_startup_info()

    try:
        from waitress import serve
        serve(
            app,
            host=HOST,
            port=PORT,
            threads=4,
            clear_untrusted_proxy_headers=True,
        )
    except ImportError:
        # Fallback apenas se waitress não estiver instalado.
        app.run(
            host=HOST,
            port=PORT,
            debug=False,
            use_reloader=False,
        )
