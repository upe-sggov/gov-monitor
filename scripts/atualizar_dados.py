"""
Gov Monitor — recolha semanal de dados da API do INE.
 
Executado pelo GitHub Actions (.github/workflows/atualizar-dados.yml).
Lê o catálogo de indicadores e grava, para cada indicador com código INE
(varcd), o ficheiro data/dados_<varcd>.json que o index.html consome.
 
Formato gravado (o index.html lê os campos «resposta» e «_recolha»):
  {"_recolha": "AAAA-MM-DD", "varcd": "...", "url": "...", "resposta": <JSON do INE>}
 
Só usa a biblioteca-padrão do Python: não requer requirements.txt.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
 
RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
CATALOGO = PASTA_DADOS / "catalogo.json"
INDEX = RAIZ / "index.html"
API = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
TENTATIVAS = 3
ESPERA_ENTRE_PEDIDOS = 1.5  # segundos, por cortesia para com a API
 
 
def carregar_catalogo():
    """Usa data/catalogo.json; se não existir, extrai o catálogo embebido no index.html."""
    if CATALOGO.exists():
        return json.loads(CATALOGO.read_text(encoding="utf-8"))
    html = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const\s+CATALOGO_EMBEBIDO\s*=\s*(\{.*?\n\});", html, re.S)
    if not m:
        sys.exit("ERRO: não encontrei data/catalogo.json nem o catálogo embebido no index.html.")
    catalogo = json.loads(m.group(1))
    PASTA_DADOS.mkdir(exist_ok=True)
    CATALOGO.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
    print("data/catalogo.json criado a partir do catálogo embebido no index.html.")
    return catalogo
 
 
def construir_url(varcd, dims):
    params = {"op": "2", "varcd": varcd, "lang": "PT"}
    params.update(dims or {})
    return f"{API}?{urllib.parse.urlencode(params)}"
 
 
def pedir(url):
    pedido = urllib.request.Request(url, headers={
        "User-Agent": "gov-monitor/1.0 (SGGov; recolha semanal via GitHub Actions)",
        "Accept": "application/json",
    })
    ultimo_erro = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(pedido, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as erro:  # rede, timeout ou JSON inválido
            ultimo_erro = erro
            print(f"   tentativa {tentativa}/{TENTATIVAS} falhou: {erro}")
            time.sleep(5 * tentativa)
    raise RuntimeError(ultimo_erro)
 
 
def resposta_valida(resposta):
    raiz = resposta[0] if isinstance(resposta, list) and resposta else resposta
    return isinstance(raiz, dict) and bool(raiz.get("Dados"))
 
 
def main():
    catalogo = carregar_catalogo()
    PASTA_DADOS.mkdir(exist_ok=True)
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
 
    # Um ficheiro por varcd (é assim que o index.html os procura).
    alvos = {}
    for ind in catalogo.get("indicadores", []):
        if ind.get("varcd") and ind["varcd"] not in alvos:
            alvos[ind["varcd"]] = ind
    print(f"{len(alvos)} indicador(es) com código INE a recolher.")
 
    sucessos, falhas = 0, []
    for varcd, ind in alvos.items():
        url = construir_url(varcd, ind.get("dims_exemplo"))
        print(f"-> {varcd} · {ind.get('nome', '')[:70]}")
        try:
            resposta = pedir(url)
        except Exception as erro:
            falhas.append(varcd)
            print(f"   ERRO: sem resposta do INE ({erro}). Ficheiro anterior mantido.")
            continue
        if not resposta_valida(resposta):
            falhas.append(varcd)
            print(f"   AVISO: resposta sem dados (código ou dimensões inválidos?): {str(resposta)[:200]}")
            continue
        destino = PASTA_DADOS / f"dados_{varcd}.json"
        destino.write_text(json.dumps(
            {"_recolha": hoje, "varcd": varcd, "url": url, "resposta": resposta},
            ensure_ascii=False, indent=1), encoding="utf-8")
        sucessos += 1
        print(f"   gravado: data/{destino.name}")
        time.sleep(ESPERA_ENTRE_PEDIDOS)
 
    print(f"\nConcluído: {sucessos} gravado(s), {len(falhas)} com falha {falhas if falhas else ''}")
    # Falha o job apenas se nada foi recolhido, para o erro ficar visível no separador Actions.
    if alvos and sucessos == 0:
        sys.exit("ERRO: nenhum indicador recolhido. Verificar o acesso à API do INE a partir do GitHub.")
 
 
if __name__ == "__main__":
    main()
 
