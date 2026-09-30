"""
Gov Monitor — recolha semanal de dados da API do INE (v2.3).

Executado pelo GitHub Actions (.github/workflows/atualizar-dados.yml).
Para cada indicador com código INE (varcd) em data/catalogo.json:
  1. lê a metainformação (pindicaMeta.jsp) para conhecer as dimensões,
     os períodos disponíveis e o código de «Total» de cada dimensão;
  2. pede os N períodos mais recentes (Dim1), com as dimensões além da
     geografia fixadas no total (ex.: ambos os sexos, todas as idades);
  3. para desagregação no painel, pede ainda, só para Portugal (Dim2=PT),
     todas as categorias das restantes dimensões (sexo, grupo etário…);
  4. grava data/dados_<varcd>.json no formato que o index.html consome.

Se a metainformação não estiver disponível, recua para um único pedido
sem dimensões (devolve apenas o período mais recente), como na v1.

Formato gravado:
  {"_recolha": "AAAA-MM-DD", "varcd": "...", "url": "...",
   "_ordem_periodos": [...], "_totais": {"dim_3": "T", ...},
   "_desagregado": {período: [linhas de Portugal com todas as categorias]},
   "resposta": [<objeto do INE com "Dados" = {período: [linhas]}>]}

Só usa a biblioteca-padrão do Python.
"""
import functools
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

print = functools.partial(print, flush=True)  # mensagens imediatas no log do GitHub Actions

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
CATALOGO = PASTA_DADOS / "catalogo.json"
INDEX = RAIZ / "index.html"
API = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
META = "https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp"
TENTATIVAS = 2
PAUSA = 0.5
TEMPO_LIMITE = 40  # segundos por pedido
MAX_FALHAS_SEGUIDAS = 2  # indicadores sem qualquer resposta antes de desistir (INE indisponível)
PERIODOS_POR_FREQ = {"anual": 12, "trimestral": 16, "mensal": 24, "decenal": 4, "bienal": 6}
ROTULOS_TOTAL = {"total", "hm", "t", "todos", "todas", "ambos os sexos"}


# ---------------------------------------------------------------- utilidades
def carregar_catalogo():
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


def pedir(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "gov-monitor/2.0 (SGGov; recolha semanal via GitHub Actions)",
        "Accept": "application/json"})
    erro = None
    for t in range(1, TENTATIVAS + 1):
        try:
            with urllib.request.urlopen(req, timeout=TEMPO_LIMITE) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            erro = e
            print(f"   tentativa {t}/{TENTATIVAS} falhou: {e}")
            time.sleep(3 * t)
    raise RuntimeError(erro)


def url_dados(varcd, params):
    p = {"op": "2", "varcd": varcd, "lang": "PT"}
    p.update(params)
    return f"{API}?{urllib.parse.urlencode(p)}"


def raiz(resposta):
    return resposta[0] if isinstance(resposta, list) and resposta else resposta


# ----------------------------------------------------------- metainformação
def dicts(obj):
    """Percorre recursivamente o JSON e devolve todos os dicionários."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from dicts(v)


def ler_categorias(meta):
    """
    Lê as categorias de cada dimensão a partir da metainformação, sem depender
    dos nomes exatos das chaves: uma categoria é um dicionário com uma chave
    que identifica a dimensão (contém 'dim'), uma com o código (contém 'cod')
    e uma com a designação (contém 'dsg' ou 'desc').
    Devolve {n.º da dimensão: [(codigo, designacao), ...]} pela ordem do INE.
    """
    cats = {}
    for d in dicts(meta):
        chaves = {k.lower(): k for k in d if isinstance(k, str)}
        k_dim = next((chaves[k] for k in chaves if "dim" in k and "num" in k), None) or \
                next((chaves[k] for k in chaves if k.startswith("dim")), None)
        k_cod = next((chaves[k] for k in chaves if "cod" in k and "dim" not in k), None)
        k_dsg = next((chaves[k] for k in chaves if ("dsg" in k or "desc" in k) and "dim" not in k), None)
        if not (k_dim and k_cod and k_dsg):
            continue
        m = re.search(r"(\d+)", str(d[k_dim]))
        if not m:
            continue
        n = int(m.group(1))
        cats.setdefault(n, []).append((str(d[k_cod]).strip(), str(d[k_dsg]).strip()))
    return cats


def codigo_total(categorias):
    for cod, dsg in categorias:
        if dsg.lower() in ROTULOS_TOTAL or cod.upper() == "T":
            return cod
    return None


def n_periodos(ind):
    return PERIODOS_POR_FREQ.get((ind.get("periodicidade") or "").lower(), 12)


# ------------------------------------------------------------------- recolha
def recolher_serie(varcd, ind):
    """Devolve (objeto INE, ordem dos períodos, totais, url) ou None se a metainformação falhar."""
    meta = pedir(f"{META}?varcd={varcd}&lang=PT")
    cats = ler_categorias(meta)
    if not cats.get(1):
        print("   metainformação sem períodos identificáveis; recuo para um único pedido.")
        return None

    totais = {}
    for n, lista in cats.items():
        if n >= 3:
            t = codigo_total(lista)
            if t is not None:
                totais[f"dim_{n}"] = t

    # ordena os períodos pelo código (a parte numérica cresce no tempo) e fica com os N mais recentes
    periodos = sorted(cats[1], key=lambda c: re.sub(r"\D", "", c[0]).zfill(12))[-n_periodos(ind):]

    r_final, dados, ordem, url_exemplo = None, {}, [], None
    for cod, dsg in periodos:
        params = {"Dim1": cod}
        params.update({f"Dim{k.split('_')[1]}": v for k, v in totais.items()})
        url = url_dados(varcd, params)
        url_exemplo = url_exemplo or url
        try:
            r = raiz(pedir(url))
        except Exception as e:
            print(f"   período {dsg}: sem resposta ({e})")
            continue
        for periodo, linhas in ((r or {}).get("Dados") or {}).items():
            if linhas:
                dados[periodo] = linhas
                ordem.append(periodo)
                r_final = r
        time.sleep(PAUSA)
    if not dados:
        return None
    r_final["Dados"] = dados

    # desagregação para Portugal: todas as categorias das dimensões além da geografia
    desag = {}
    if totais:
        for cod, dsg in periodos:
            try:
                r2 = raiz(pedir(url_dados(varcd, {"Dim1": cod, "Dim2": "PT"})))
            except Exception as e:
                print(f"   desagregação {dsg}: sem resposta ({e})")
                continue
            for periodo, linhas in ((r2 or {}).get("Dados") or {}).items():
                if linhas:
                    desag[periodo] = linhas
            time.sleep(PAUSA)
        print(f"   desagregação para Portugal: {len(desag)} período(s)")
    return r_final, ordem, totais, url_exemplo, desag


def recolher_ultimo(varcd, ind):
    """Recuo: um único pedido (período mais recente, todas as dimensões)."""
    url = url_dados(varcd, ind.get("dims_exemplo") or {})
    r = raiz(pedir(url))
    if not r or not r.get("Dados"):
        return None
    return r, list(r["Dados"].keys()), {}, url, {}


def main():
    catalogo = carregar_catalogo()
    PASTA_DADOS.mkdir(exist_ok=True)
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    alvos = {}
    for ind in catalogo.get("indicadores", []):
        if ind.get("varcd") and ind["varcd"] not in alvos:
            alvos[ind["varcd"]] = ind
    print(f"{len(alvos)} indicador(es) com código INE a recolher.")

    sucessos, falhas, seguidas = 0, [], 0
    for varcd, ind in alvos.items():
        if seguidas >= MAX_FALHAS_SEGUIDAS:
            print(f"\nA API do INE não respondeu a {seguidas} indicadores seguidos: recolha interrompida.")
            print("Os ficheiros anteriores foram mantidos. Voltar a correr mais tarde.")
            falhas += [v for v in alvos if v not in falhas and not (PASTA_DADOS / f"dados_{v}.json").exists()]
            break
        print(f"-> {varcd} · {ind.get('nome', '')[:70]}")
        resultado = None
        try:
            resultado = recolher_serie(varcd, ind)
        except Exception as e:
            print(f"   metainformação indisponível ({e}); recuo para um único pedido.")
        if resultado is None:
            try:
                resultado = recolher_ultimo(varcd, ind)
            except Exception as e:
                print(f"   ERRO: sem resposta do INE ({e}). Ficheiro anterior mantido.")
        if resultado is None:
            falhas.append(varcd)
            seguidas += 1
            print("   AVISO: resposta sem dados. Ficheiro anterior mantido.")
            continue
        seguidas = 0
        r, ordem, totais, url, desag = resultado
        destino = PASTA_DADOS / f"dados_{varcd}.json"
        destino.write_text(json.dumps({
            "_recolha": hoje, "varcd": varcd, "url": url,
            "_ordem_periodos": ordem, "_totais": totais, "_desagregado": desag, "resposta": [r]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        sucessos += 1
        print(f"   gravado: data/{destino.name} · {len(ordem)} período(s) · totais {totais or '—'}")

    print(f"\nConcluído: {sucessos} gravado(s), {len(falhas)} com falha {falhas if falhas else ''}")
    if alvos and sucessos == 0:
        sys.exit("ERRO: nenhum indicador recolhido. Verificar o acesso à API do INE a partir do GitHub.")


if __name__ == "__main__":
    main()
