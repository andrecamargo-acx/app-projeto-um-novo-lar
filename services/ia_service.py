# %% [markdown]
# # services/ia_service.py
# Integração com o Gemini.
# Contém:
# - gerar_resumo_pessoa_ia: resumo empático do caso
# - classificar_pessoa_ia: prioridade + tags + próximos passos

import json as pyjson
import google.generativeai as genai
from config import Config

# %% [markdown]
# ## Inicialização do modelo
# Configura a API Key e carrega o modelo.
# Se não houver chave, o serviço funciona em modo degradado (sem IA).
gemini_model = None
if Config.GEMINI_API_KEY:
    genai.configure(api_key=Config.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel(Config.GEMINI_MODEL)


def gerar_resumo_pessoa_ia(pessoa: dict) -> str:
    # %% [markdown]
    # ## gerar_resumo_pessoa_ia
    # Gera um resumo em até 2 parágrafos baseado nas informações do cadastro.
    if not gemini_model:
        return "IA não configurada (GEMINI_API_KEY ausente)."

    contexto = f"""
Nome: {pessoa.get('nome') or 'Não informado'}
Gênero: {pessoa.get('genero') or 'Não informado'}
Data de nascimento: {pessoa.get('data_nascimento') or 'Não informada'}
Cidade de origem: {pessoa.get('cidade_origem') or 'Não informada'}
Situação de rua desde: {pessoa.get('situacao_rua_desde') or 'Não informada'}
Resumo de saúde: {pessoa.get('saude_resumo') or 'Não informado'}
Dependências químicas: {pessoa.get('dependencias_quimicas') or 'Não informado'}
Rede de apoio: {pessoa.get('rede_apoio') or 'Não informada'}
Profissão anterior: {pessoa.get('profissao_anterior') or 'Não informado'}
Observações gerais: {pessoa.get('observacoes') or 'Sem observações'}
"""

    prompt = f"""
Você é um assistente social que escreve resumos de forma empática e objetiva.

Abaixo estão informações estruturadas sobre uma pessoa acolhida.
Gere um resumo em português, claro e humano, em até 2 parágrafos, destacando:
- contexto geral da pessoa
- pontos de atenção (saúde, documentos, dependência, rede de apoio)
- sem fazer diagnósticos médicos, apenas descrevendo a situação.

Texto para analisar:
{contexto}
"""

    resp = gemini_model.generate_content(prompt)
    return (resp.text or "").strip()

# %% [markdown]
# ## classificar_pessoa_ia()
# - Classifica prioridade
# - Extrai tags
# - Sugere próximos passos
# - Sugere perguntas para a próxima entrevista/acompanhamento
#
# Retorna dict:
# {
#   "prioridade": "...",
#   "tags": "tag1;tag2;...",
#   "proximos_passos": "...",
#   "perguntas": "Pergunta 1\nPergunta 2..."
# }

import json as pyjson


def _limpar_bloco_codigo(texto: str) -> str:
    # remove ```json ... ``` ou ``` ... ```
    t = (texto or "").strip()
    if t.startswith("```"):
        # remove primeira linha (``` ou ```json)
        linhas = t.splitlines()
        linhas = linhas[1:]
        # remove última linha se for ```
        if linhas and linhas[-1].strip().startswith("```"):
            linhas = linhas[:-1]
        t = "\n".join(linhas).strip()
    return t


def classificar_pessoa_ia(pessoa: dict) -> dict:
    if not gemini_model:
        return {
            "prioridade": "desconhecida",
            "tags": "",
            "proximos_passos": "IA não configurada (GEMINI_API_KEY ausente).",
            "perguntas": "",
        }

    contexto = f"""
Gênero: {pessoa.get('genero') or 'Não informado'}
Data de nascimento: {pessoa.get('data_nascimento') or 'Não informada'}
Cidade de origem: {pessoa.get('cidade_origem') or 'Não informada'}
Situação de rua desde: {pessoa.get('situacao_rua_desde') or 'Não informada'}
Resumo de saúde: {pessoa.get('saude_resumo') or 'Não informado'}
Dependências químicas: {pessoa.get('dependencias_quimicas') or 'Não informado'}
Possui documentos básicos: {"Sim" if pessoa.get("tem_documentos") else "Não"}
Rede de apoio: {pessoa.get('rede_apoio') or 'Não informada'}
Profissão anterior: {pessoa.get('profissao_anterior') or 'Não informado'}
Avaliação médica: {pessoa.get('avaliacao_medica') or 'Não informada'}
Avaliação psicológica: {pessoa.get('avaliacao_psicologica') or 'Não informada'}
Observações gerais: {pessoa.get('observacoes') or 'Sem observações'}
"""

    prompt = f"""
Você é um profissional de assistência social que organiza casos de pessoas em situação de vulnerabilidade.

Responda ESTRITAMENTE em JSON, sem texto fora do JSON, no formato:

{{
  "prioridade": "alta" | "media" | "baixa",
  "tags": ["tag1", "tag2", ...],
  "proximos_passos": "texto em português com sugestões objetivas",
  "perguntas": ["pergunta 1", "pergunta 2", "pergunta 3"]
}}

Regras:
- As tags devem ser curtas em snake_case. Ex.: "sem_documentos", "saude_mental", "dependencia_quimica", "sem_rede_apoio"
- Não faça diagnósticos médicos. Apenas descreva e oriente.
- Em "perguntas", sugira perguntas que a equipe pode fazer na próxima entrevista.

Informações da pessoa:
{contexto}
"""

    resp = gemini_model.generate_content(prompt)
    texto = _limpar_bloco_codigo((resp.text or "").strip())

    try:
        data = pyjson.loads(texto)
    except Exception:
        return {
            "prioridade": "desconhecida",
            "tags": "",
            "proximos_passos": "Não foi possível interpretar a resposta da IA.",
            "perguntas": "",
        }

    prioridade = data.get("prioridade", "desconhecida")
    tags_list = data.get("tags", [])
    tags_str = ";".join(str(t) for t in tags_list) if isinstance(tags_list, list) else str(tags_list)

    proximos_passos = (data.get("proximos_passos") or "").strip()

    perguntas = data.get("perguntas", [])
    if isinstance(perguntas, list):
        perguntas_str = "\n".join([str(p).strip() for p in perguntas if str(p).strip()])
    else:
        perguntas_str = str(perguntas).strip()

    return {
        "prioridade": prioridade,
        "tags": tags_str,
        "proximos_passos": proximos_passos,
        "perguntas": perguntas_str,
    }

