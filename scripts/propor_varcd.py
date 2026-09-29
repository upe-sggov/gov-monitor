"""
Gov Monitor — proposta de códigos INE (varcd) para o catálogo.

Descarrega o catálogo oficial de indicadores do INE (API xml_indic.jsp),
compara-o com as entradas de data/catalogo.json que ainda não têm varcd
e grava data/propostas_varcd.csv com os 3 melhores candidatos por entrada.

NÃO altera o catálogo: as propostas têm de ser validadas antes de o varcd
ser copiado para data/catalogo.json.

Fontes (documentação oficial da API do INE):
  opc=3 -> «Principais Indicadores» (~260)
  opc=2 -> catálogo completo (~10 000), usado para as entradas sem boa correspondência
"""
import csv
import json
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = RAIZ / "data" / "catalogo.json"
SAIDA = RAIZ / "data" / "propostas_varcd.csv"
URL_CAT = "https://www.ine.pt/ine/xml_indic.jsp?opc={opc}&lang=PT"
LIMIAR_BOA = 0.55  # abaixo disto, a entrada é procurada também no catálogo completo

PARAGENS = set("""a o as os de da do das dos e em no na nos nas por para com sem um uma
ao aos à às pelo pela pelos pelas segundo total valor n nº º taxa""".split())


def normalizar(texto):
    t = unicodedata.normalize("NFKD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return [p for p in re.findall(r"[a-z0-9]+", t) if p not in PARAGENS and len(p) > 1]


def descarregar(opc):
    print(f"A descarregar catálogo do INE (opc={opc})…")
    req = urllib.request.Request(URL_CAT.format(opc=opc),
                                 headers={"User-Agent": "gov-monitor/1.0 (SGGov)"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def ler_catalogo_ine(xml_bytes):
    """Leitura genérica: cada elemento que contém <varcd> é um indicador."""
    raiz = ET.fromstring(xml_bytes)
    indicadores = []
    for el in raiz.iter():
        filhos = {re.sub(r"^\{.*\}", "", f.tag).lower(): (f.text or "").strip() for f in el}
        if filhos.get("varcd"):
            titulo = next((filhos[k] for k in ("title", "titulo", "designacao", "designation", "ind_designation")
                           if filhos.get(k)), "")
            if not titulo:  # recurso: o campo de texto mais longo
                titulo = max((v for k, v in filhos.items() if k not in ("varcd",) and not v.startswith("http")),
                             key=len, default="")
            filhos["_titulo"] = titulo
            indicadores.append(filhos)
    print(f"   {len(indicadores)} indicadores lidos.")
    return indicadores


def pontuar(nome, titulo):
    a, b = set(normalizar(nome)), set(normalizar(titulo))
    if not a or not b:
        return 0.0
    comuns = a & b
    return round(0.7 * len(comuns) / len(a) + 0.3 * len(comuns) / len(a | b), 3)


def candidatos(entrada, ine, n=3):
    lista = []
    for ind in ine:
        s = pontuar(entrada["nome"], ind["_titulo"])
        per = (entrada.get("periodicidade") or "").lower()
        if per and per[:4] in " ".join(ind.values()).lower():
            s += 0.05
        if s >= 0.15:  # ignora correspondências sem palavras em comum relevantes
            lista.append((round(s, 2), ind))
    lista.sort(key=lambda x: x[0], reverse=True)
    return lista[:n]


def main():
    if not CATALOGO.exists():
        sys.exit("ERRO: data/catalogo.json não existe. Correr primeiro o workflow «Atualizar dados do INE».")
    cat = json.loads(CATALOGO.read_text(encoding="utf-8"))
    pendentes = [i for i in cat.get("indicadores", []) if not i.get("varcd")]
    print(f"{len(pendentes)} entrada(s) sem código INE.")

    principais = ler_catalogo_ine(descarregar(3))
    completo = None
    linhas = []
    for e in pendentes:
        melhores = candidatos(e, principais)
        origem = "Principais Indicadores (opc=3)"
        if not melhores or melhores[0][0] < LIMIAR_BOA:
            if completo is None:
                completo = ler_catalogo_ine(descarregar(2))
            alt = candidatos(e, completo)
            if alt and (not melhores or alt[0][0] > melhores[0][0]):
                melhores, origem = alt, "Catálogo completo (opc=2)"
        for pos, (s, ind) in enumerate(melhores, 1):
            v = ind["varcd"]
            linhas.append({
                "id_catalogo": e["id"], "nome_catalogo": e["nome"], "area": e.get("area", ""),
                "candidato": pos, "varcd_proposto": v, "titulo_INE": ind["_titulo"],
                "confianca": s, "origem": origem,
                "ficha_INE": f"https://www.ine.pt/xurl/indx/{v}/PT",
                "metainformacao": f"https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd={v}&lang=PT",
                "validado": "",
            })
        top = melhores[0] if melhores else (0, {"varcd": "-", "_titulo": "-"})
        print(f"-> {e['id']}: {top[1]['varcd']} ({top[0]}) {top[1]['_titulo'][:70]}")

    with SAIDA.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()) if linhas else ["id_catalogo"], delimiter=";")
        w.writeheader(); w.writerows(linhas)
    print(f"\nGravado data/{SAIDA.name}: {len(linhas)} proposta(s) para validação.")


if __name__ == "__main__":
    main()
