from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

APP_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = APP_DIR / "database" / "database.db"

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS associados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cpf TEXT,
        telefone TEXT,
        email TEXT,
        lote TEXT,
        endereco TEXT,
        usuario TEXT NOT NULL UNIQUE,
        senha_hash TEXT NOT NULL,
        tipo TEXT NOT NULL CHECK(tipo IN ('admin', 'usuario')) DEFAULT 'usuario',
        status TEXT NOT NULL CHECK(status IN ('ativo', 'inativo')) DEFAULT 'ativo',
        data_cadastro TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        associado_id INTEGER NOT NULL,
        valor REAL NOT NULL,
        data_vencimento TEXT NOT NULL,
        data_pagamento TEXT,
        status TEXT NOT NULL CHECK(status IN ('pendente', 'pago', 'atrasado')) DEFAULT 'pendente',
        forma_pagamento TEXT CHECK(forma_pagamento IN ('pix', 'dinheiro', 'transferencia')),
        observacao TEXT,
        comprovante_path TEXT,
        FOREIGN KEY (associado_id) REFERENCES associados(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reunioes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        data TEXT NOT NULL,
        descricao TEXT,
        ata TEXT,
        presenca TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS avisos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titulo TEXT NOT NULL,
        mensagem TEXT NOT NULL,
        data TEXT NOT NULL,
        prioridade TEXT NOT NULL CHECK(prioridade IN ('baixa', 'média', 'alta')) DEFAULT 'média'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projetos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        descricao TEXT,
        status TEXT NOT NULL CHECK(status IN ('planejado', 'andamento', 'concluido')) DEFAULT 'planejado',
        valor_previsto REAL NOT NULL DEFAULT 0,
        valor_arrecadado REAL NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        acao TEXT NOT NULL,
        data TEXT NOT NULL,
        FOREIGN KEY (usuario_id) REFERENCES associados(id) ON DELETE SET NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pagamentos_assoc ON pagamentos(associado_id)",
    "CREATE INDEX IF NOT EXISTS idx_pagamentos_status ON pagamentos(status)",
    "CREATE INDEX IF NOT EXISTS idx_pagamentos_vencimento ON pagamentos(data_vencimento)",
    "CREATE INDEX IF NOT EXISTS idx_logs_data ON logs(data)",
]


def get_connection() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connection_context() -> Iterable[sqlite3.Connection]:
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def insert(query: str, params: tuple[Any, ...] = ()) -> int:
    with connection_context() as connection:
        cursor = connection.execute(query, params)
        return int(cursor.lastrowid)


def execute(query: str, params: tuple[Any, ...] = ()) -> int:
    with connection_context() as connection:
        cursor = connection.execute(query, params)
        return int(cursor.rowcount)


def execute_many(query: str, params_list: list[tuple[Any, ...]]) -> int:
    if not params_list:
        return 0

    with connection_context() as connection:
        cursor = connection.executemany(query, params_list)
        return int(cursor.rowcount)


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    connection = get_connection()
    try:
        cursor = connection.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    connection = get_connection()
    try:
        cursor = connection.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def record_log(usuario_id: int | None, acao: str) -> None:
    insert(
        """
        INSERT INTO logs (usuario_id, acao, data)
        VALUES (?, ?, ?)
        """,
        (usuario_id, acao, datetime.now().isoformat(timespec="seconds")),
    )


def init_db() -> None:
    with connection_context() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)

    seed_default_admin()


def seed_default_admin() -> None:
    admin_exists = fetch_one("SELECT id FROM associados WHERE usuario = ?", ("admin",))
    if admin_exists:
        return

    default_password_hash = hashlib.sha256("123456".encode("utf-8")).hexdigest()
    admin_id = insert(
        """
        INSERT INTO associados (
            nome,
            cpf,
            telefone,
            email,
            lote,
            endereco,
            usuario,
            senha_hash,
            tipo,
            status,
            data_cadastro
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Administrador do Sistema",
            "",
            "",
            "admin@associacao.local",
            "Admin",
            "",
            "admin",
            default_password_hash,
            "admin",
            "ativo",
            datetime.now().date().isoformat(),
        ),
    )
    record_log(admin_id, "Usuário administrador padrão criado automaticamente")
