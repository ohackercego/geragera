#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interface web para gerar imagens com a API gratuita da NVIDIA.
100% biblioteca padrao do Python (http.server). Sem instalacoes.

Uso:
  python nvidia_imagem_web.py            (porta 8000)
  python nvidia_imagem_web.py --porta 9000

Depois abra no navegador:  http://localhost:8000

A chave da API e pedida UMA unica vez e salva CRIPTOGRAFADA no arquivo
~/.nvidia_api_key.enc (DPAPI do Windows: so o mesmo usuario, na mesma
maquina, consegue decifrar). Nas proximas aberturas a pagina nao pede a
chave de novo - voce so escreve o prompt e gera. Para trocar a chave,
clique em "Trocar chave".

Recursos da pagina:
  - Campo de prompt (sempre visivel)
  - Botoes: Gerar imagem e Baixar imagem
  - A imagem gerada e salva em saidas/

Modelo usado (verificado em 09/08/2026):
  - black-forest-labs/flux.1-dev: texto -> imagem
  - Endpoint: https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev
"""

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime

import nvidia_dpapi

BASE_URL = "https://ai.api.nvidia.com/v1/genai"
MODELO_GERAR = "black-forest-labs/flux.1-dev"
TIMEOUT = 300
CHAVE_ARQ_PLAIN = Path.home() / ".nvidia_api_key"  # fallback antigo
DIMENSOES_VALIDAS = [768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280, 1344]


def base_dir():
    """Pasta do exe (quando empacotado) ou do script (em dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


PASTA_SAIDAS = base_dir() / "saidas"

# ----------------------------------------------------------------------------
# Pagina HTML
# ----------------------------------------------------------------------------

PAGINA = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gerador de Imagens NVIDIA</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: "Segoe UI", Arial, sans-serif; background: #101418; color: #e8eaed;
         max-width: 760px; margin: 0 auto; padding: 24px 16px; line-height: 1.5; }
  h1 { font-size: 1.4em; margin-bottom: 4px; }
  .sub { color: #9aa0a6; font-size: .9em; margin-top: 0; }
  label { display: block; margin-top: 16px; font-weight: 600; }
  input[type=password], input[type=text], input[type=number], textarea, select {
    width: 100%; padding: 10px; margin-top: 6px; border-radius: 8px;
    border: 1px solid #3c4043; background: #1b2127; color: #e8eaed; font-size: 1em; }
  textarea { min-height: 90px; resize: vertical; }
  button { margin-top: 20px; padding: 12px 24px; font-size: 1.05em; font-weight: 700;
           background: #4c8bf5; color: #fff; border: 0; border-radius: 8px; cursor: pointer; }
  button:hover { background: #3b77e0; }
  button.pequeno { margin-top: 10px; padding: 8px 14px; font-size: .95em; background: #3d4650; }
  .opcoes { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
  .status { margin-top: 18px; padding: 12px 14px; border-radius: 8px; white-space: pre-wrap; }
  .ok { background: #14381f; border: 1px solid #2e7d43; }
  .erro { background: #3d1414; border: 1px solid #b3261e; }
  .info { background: #1c2a3d; border: 1px solid #3c5a8a; }
  .img { margin-top: 18px; text-align: center; }
  .img img { max-width: 100%; border-radius: 8px; border: 1px solid #3c4043; }
  .img a { display: inline-block; margin-top: 10px; color: #8ab4f8; text-decoration: none;
           border: 1px solid #8ab4f8; padding: 8px 16px; border-radius: 6px; }
  .img a:hover { background: #1c2a3d; }
  .obs { color: #9aa0a6; font-size: .85em; margin-top: 24px; }
  .chave-save { background: #14381f; border: 1px solid #2e7d43; border-radius: 8px;
                padding: 12px 14px; margin-top: 16px; }
  .chave-save a { color: #8ab4f8; }
</style>
</head>
<body>
  <h1>Gerador de Imagens NVIDIA</h1>
  <p class="sub">flux.1-dev - API gratuita da NVIDIA</p>

  {secao_chave}

  <form method="post" action="/gerar">
    <label for="prompt">O que gerar</label>
    <textarea id="prompt" name="prompt" required
              placeholder="Ex.: um gato astronauta flutuando no espaco, estilo cartoon"></textarea>

    <div class="opcoes">
      <div>
        <label for="largura">Largura</label>
        <input type="number" id="largura" name="largura" value="1024" min="768" max="1344" step="64">
      </div>
      <div>
        <label for="altura">Altura</label>
        <input type="number" id="altura" name="altura" value="1024" min="768" max="1344" step="64">
      </div>
      <div>
        <label for="passos">Passos</label>
        <input type="number" id="passos" name="passos" value="50" min="5" max="100">
      </div>
      <div>
        <label for="escala">Escala (1-9)</label>
        <input type="number" id="escala" name="escala" value="3.5" min="1.1" max="9" step="0.1">
      </div>
    </div>

    <button type="submit">Gerar imagem</button>
  </form>

  <div class="status" id="status" role="status" aria-live="polite">{status}</div>

  <p class="obs">A chave, quando informada, e salva criptografada em ~/.nvidia_api_key.enc
  (so este usuario, nesta maquina, consegue usa-la). As imagens ficam em: saidas/</p>
</body>
</html>"""


def secao_chave(mostrar_campo):
    """Bloco da chave: campo para digitar (primeira vez / trocar) ou aviso de salva."""
    if mostrar_campo:
        return """
  <form method="post" action="/salvar-chave">
    <label for="chave">Chave da API NVIDIA</label>
    <input type="password" id="chave" name="chave" autocomplete="off"
           placeholder="nvapi-... (salva criptografada neste computador)">
    <button type="submit" class="pequeno">Salvar chave criptografada</button>
  </form>"""
    return """
  <div class="chave-save" role="status">
    Chave da API salva e criptografada neste computador. <a href="/?trocar=1">Trocar chave</a>
  </div>"""


def renderizar(status_html="", mostrar_campo=False):
    html = PAGINA.replace("{secao_chave}", secao_chave(mostrar_campo))
    return html.replace("{status}", status_html).encode("utf-8")


# ----------------------------------------------------------------------------
# Chave
# ----------------------------------------------------------------------------

def obter_chave(form):
    """Chave: campo digitado > chave criptografada salva > env > arquivo antigo."""
    chave = (form.get("chave") or "").strip()
    if chave:
        return chave, "digitada"
    chave = nvidia_dpapi.ler_chave_salva()
    if chave:
        return chave, "salva"
    env = os.environ.get("NVIDIA_API_KEY")
    if env:
        return env.strip(), "env"
    if CHAVE_ARQ_PLAIN.exists():
        chave = CHAVE_ARQ_PLAIN.read_text(encoding="utf-8").strip()
        if chave:
            return chave, "arquivo"
    return None, None


# ----------------------------------------------------------------------------
# API NVIDIA
# ----------------------------------------------------------------------------

def chamar_api(url, chave, payload):
    """Envia JSON para a NVIDIA e devolve (resposta_dict, erro_str)."""
    headers = {
        "Authorization": f"Bearer {chave}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", errors="replace")[:500]
        return None, (e.code, detalhe)
    except Exception as e:
        return None, ("erro", str(e))


def detectar_extensao(bytes_img):
    if bytes_img[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if bytes_img[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    return ".jpg"


def extrair_imagem(resposta):
    """Devolve (bytes_da_imagem, seed) ou levanta ValueError."""
    if not isinstance(resposta, dict):
        raise ValueError("Resposta invalida da API.")
    if "artifacts" in resposta:
        artefato = resposta["artifacts"][0]
        razao = artefato.get("finishReason")
        if razao == "ERROR":
            raise ValueError("O modelo retornou ERROR (falha interna).")
        b64 = artefato.get("base64")
        if b64:
            return base64.b64decode(b64), artefato.get("seed")
    if "error" in resposta:
        raise ValueError(json.dumps(resposta["error"], ensure_ascii=False)[:400])
    raise ValueError("A API nao devolveu imagem.")


def gerar(args):
    """Chama a API e devolve (bytes_img, extensao, nome_arquivo, mensagem)."""
    chave, origem = obter_chave(args)
    if not chave:
        raise ValueError("Chave da API nao informada. Digite a chave no campo acima.")

    prompt = (args.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Escreva o prompt no campo 'O que gerar'.")

    try:
        largura = int(args.get("largura", 1024))
        altura = int(args.get("altura", 1024))
        passos = int(args.get("passos", 50))
        escala = float(args.get("escala", 3.5))
    except ValueError:
        raise ValueError("Largura, altura, passos e escala devem ser numeros.")
    if largura not in DIMENSOES_VALIDAS or altura not in DIMENSOES_VALIDAS:
        raise ValueError("Largura/altura validas: " + ", ".join(map(str, DIMENSOES_VALIDAS)))
    if not (5 <= passos <= 100):
        raise ValueError("Passos deve estar entre 5 e 100.")
    if not (1 < escala <= 9):
        raise ValueError("Escala deve estar entre 1 e 9.")

    url = f"{BASE_URL}/{MODELO_GERAR}"
    payload = {
        "prompt": prompt,
        "cfg_scale": escala,
        "seed": 0,
        "steps": passos,
        "width": largura,
        "height": altura,
    }
    descricao = f"Gerando imagem {largura}x{altura} (flux.1-dev)"

    resposta, erro = chamar_api(url, chave, payload)
    if erro:
        codigo, detalhe = erro
        if codigo in (401, 403) and origem == "salva":
            raise ValueError(
                "A chave salva nao foi aceita pela API (erro de autenticacao). "
                "Clique em 'Trocar chave' e informe a chave correta.")
        raise ValueError(f"Falha na chamada a API (HTTP {codigo}): {detalhe}")

    img = extrair_imagem(resposta)
    bytes_img, seed = img
    extensao = detectar_extensao(bytes_img)

    # Pede a chave UMA vez: se o usuario digitou e gerou com sucesso, salva criptografada
    if origem == "digitada":
        try:
            nvidia_dpapi.salvar_chave_criptografada(chave)
            nota_chave = "\nChave salva criptografada (nao sera pedida de novo)."
        except Exception:
            nota_chave = ""
    else:
        nota_chave = ""

    PASTA_SAIDAS.mkdir(parents=True, exist_ok=True)
    nome = "imagem_" + datetime.now().strftime("%Y%m%d_%H%M%S") + extensao
    arquivo = PASTA_SAIDAS / nome
    arquivo.write_bytes(bytes_img)

    msg = f"{descricao} concluida com sucesso.{nota_chave}\nSalvo em: saidas/{nome} ({len(bytes_img)//1024} KB)"
    if seed:
        msg += f"\nSemente: {seed}"
    return bytes_img, extensao, nome, msg


# ----------------------------------------------------------------------------
# Servidor
# ----------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def _enviar(self, corpo, ctype="text/html; charset=utf-8", code=200, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corpo)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        import urllib.parse
        caminho = urllib.parse.urlparse(self.path).path
        if caminho in ("/", "/index.html"):
            mostrar = "trocar=1" in self.path or not nvidia_dpapi.chave_esta_salva()
            self._enviar(renderizar(mostrar_campo=mostrar))
        elif caminho.startswith("/baixar/"):
            nome = Path(self.path.split("/", 2)[2]).name  # so o nome, sem subpastas
            arquivo = PASTA_SAIDAS / nome
            if not arquivo.exists() or not arquivo.is_file():
                self._enviar(b"<h1>404: arquivo nao encontrado</h1>", code=404)
                return
            dados = arquivo.read_bytes()
            self._enviar(dados, ctype="application/octet-stream",
                         extra={"Content-Disposition": f'attachment; filename="{nome}"'})
        else:
            self._enviar(b"<h1>404</h1>", code=404)

    def do_POST(self):
        import urllib.parse
        if self.path not in ("/gerar", "/salvar-chave"):
            self._enviar(b"<h1>404</h1>", code=404)
            return
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            corpo = self.rfile.read(tamanho).decode("utf-8", errors="replace")
            form = dict(urllib.parse.parse_qsl(corpo, keep_blank_values=True))

            if self.path == "/salvar-chave":
                chave = (form.get("chave") or "").strip()
                if not chave:
                    status = '<div class="status erro">Erro: digite a chave antes de salvar.</div>'
                    self._enviar(renderizar(status, mostrar_campo=True))
                    return
                if nvidia_dpapi.salvar_chave_criptografada(chave):
                    status = '<div class="status ok">Chave salva criptografada em ~/.nvidia_api_key.enc</div>'
                    self._enviar(renderizar(status, mostrar_campo=False))
                else:
                    status = '<div class="status erro">Erro: nao foi possivel salvar a chave.</div>'
                    self._enviar(renderizar(status, mostrar_campo=True))
                return

            # /gerar
            bytes_img, ext, nome, msg = gerar(form)
            b64 = base64.b64encode(bytes_img).decode()
            mime = "image/jpeg" if ext == ".jpg" else "image/png"
            status = f'<div class="status ok">{msg}</div>'
            status += (f'<div class="img"><img src="data:{mime};base64,{b64}" '
                       f'alt="Imagem gerada">'
                       f'<a href="/baixar/{nome}">Baixar imagem</a></div>')
            self._enviar(renderizar(status, mostrar_campo=False))
        except ValueError as e:
            status = f'<div class="status erro">Erro: {e}</div>'
            self._enviar(renderizar(status, mostrar_campo=True))
        except Exception as e:
            status = f'<div class="status erro">Erro interno: {e}</div>'
            self._enviar(renderizar(status, mostrar_campo=True))

    def log_message(self, fmt, *args):
        # Logs apenas de caminho/status, nunca de chave ou prompt.
        sys.stderr.write(f"[web] {self.address_string()} {fmt % args}\n")


def main():
    parser = argparse.ArgumentParser(prog="nvidia_imagem_web", description=__doc__)
    parser.add_argument("--porta", type=int, default=8000, help="Porta (padrao 8000)")
    args = parser.parse_args()
    servidor = ThreadingHTTPServer(("127.0.0.1", args.porta), Handler)
    print(f"[ok] Servidor web rodando em http://localhost:{args.porta}")
    print("[ok] Abra essa pagina no navegador. Para parar: Ctrl+C")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[ok] Servidor parado.")


if __name__ == "__main__":
    main()
