"""Regras de privacidade (LGPD): mascaramento de dados pessoais em títulos e nomes de elementos.

O agente NUNCA grava o que é digitado, só a QUANTIDADE de caracteres e o nome do campo.
"""
import re

import config

_PADROES = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[cnpj]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[cpf]"),
    (re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"), "[cartao]"),
    (re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b"), "[telefone]"),
]


def mascarar(texto):
    """Substitui e-mails, CPFs, CNPJs, cartões e telefones por marcadores."""
    if not texto:
        return texto or ""
    for padrao, marcador in _PADROES:
        texto = padrao.sub(marcador, texto)
    return texto


def titulo_sensivel(titulo):
    t = (titulo or "").lower()
    return any(termo in t for termo in config.TERMOS_SENSIVEIS_TITULO)
