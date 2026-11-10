"""Sugestões de melhoria (melhorias.py)."""
import melhorias


def test_sugestoes_da_empresa_demo(banco, empresa_demo):
    con = banco.conectar()
    itens = []
    for email in ("ana.souza@demo.com.br", "bruno.lima@demo.com.br"):
        c = empresa_demo[email]
        itens.append((c, banco.carregar_resultado(con, c["usuario_coleta"]), lambda pid: "#" + pid))
    lista = melhorias.da_empresa(itens)
    tipos = {i["tipo"] for i in lista}
    assert {"copiar_colar", "mover_arquivo", "email_manual", "redigitacao"} <= tipos
    assert len({i["chave"] for i in lista}) == len(lista)          # chaves únicas
    ordem = {"alto": 0, "rapido": 1, "avaliar": 2}
    assert [ordem[i["prioridade"]] for i in lista] == sorted(ordem[i["prioridade"]] for i in lista)


def test_prioridade():
    assert melhorias._prioridade(0.2, "baixo")[0] == "rapido"
    assert melhorias._prioridade(1.5, "alto")[0] == "alto"
    assert melhorias._prioridade(0.3, "medio")[0] == "avaliar"
