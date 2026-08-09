#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador de imagens com a API gratuita da NVIDIA (build.nvidia.com / NIM).

IMPORTANTE (verificado em 09/08/2026 com chave real):
  - qwen-image e qwen-image-edit NAO tem endpoint hospedado gratuito
    (no site aparecem como "Downloadable" = self-host: voce precisaria de
    uma GPU e rodar o container NGC). Por isso o programa usa o modelo
    FREE com endpoint hospedado que funciona de verdade:

  - black-forest-labs/flux.1-dev: GERA imagem a partir de texto.
    Endpoint: https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev

Requisitos: Python 3.9+ (apenas biblioteca padrao, sem pip install).
API key da NVIDIA (gratuita em https://build.nvidia.com -> botao "Get API Key").

Modos de fornecimento da chave (ordem de prioridade):
  1. Argumento --chave KEY
  2. Variavel de ambiente NVIDIA_API_KEY
  3. Chave criptografada salva em ~/.nvidia_api_key.enc (--salvar-chave)
  4. Arquivo antigo ~/.nvidia_api_key (uma linha com a chave)

Exemplos:
  # Gerar imagem
  python nvidia_imagem.py gerar "um gato astronauta flutuando no espaco, estilo cartoon" --saida gato.png

  # Gerar com parametros finos (dimensoes validas do flux: 768, 832, 896, 960,
  # 1024, 1088, 1152, 1216, 1280 ou 1344)
  python nvidia_imagem.py gerar "poster cyberpunk de cidade futurista" --largura 1344 --altura 768 --passos 40 --escala 5 --saida poster.png

  # Teste offline (nao gasta credito, nao precisa de chave)
  python nvidia_imagem.py gerar "teste" --teste --saida teste.png
"""

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

import nvidia_dpapi

# ----------------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------------

BASE_URL = "https://ai.api.nvidia.com/v1/genai"
MODELO = "black-forest-labs/flux.1-dev"
TIMEOUT = 300  # geracao de imagem pode demorar
CHAVE_ARQ = Path.home() / ".nvidia_api_key"

# Dimensoes aceitas pelo flux.1-dev (so estes valores)
DIMENSOES_VALIDAS = [768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280, 1344]


# ----------------------------------------------------------------------------
# Chave da API
# ----------------------------------------------------------------------------

def obter_chave(arg_chave):
    """Chave na ordem: argumento > criptografada salva > variavel > arquivo antigo."""
    if arg_chave:
        return arg_chave.strip()
    chave = nvidia_dpapi.ler_chave_salva()
    if chave:
        return chave
    env = os.environ.get("NVIDIA_API_KEY")
    if env:
        return env.strip()
    if CHAVE_ARQ.exists():
        chave = CHAVE_ARQ.read_text(encoding="utf-8").strip()
        if chave:
            return chave
    return None


def salvar_chave(chave):
    """Grava a chave CRIPTOGRAFADA em ~/.nvidia_api_key.enc (DPAPI no Windows)."""
    if nvidia_dpapi.salvar_chave_criptografada(chave):
        print(f"[ok] Chave salva criptografada em {nvidia_dpapi.ARQUIVO_CHAVE_ENC}")
    else:
        print("[erro] Nao foi possivel salvar a chave criptografada.")


# ----------------------------------------------------------------------------
# Chamada a API
# ----------------------------------------------------------------------------

def chamar_api(url, chave, payload):
    """Envia a requisicao JSON para a NVIDIA e devolve (resposta, erro)."""
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
        detalhe = e.read().decode("utf-8", errors="replace")[:600]
        return None, (e.code, detalhe)
    except Exception as e:
        return None, ("erro", str(e))


# ----------------------------------------------------------------------------
# Salvamento da imagem
# ----------------------------------------------------------------------------

def detectar_extensao(bytes_img):
    """Descobre o formato real pelos primeiros bytes."""
    if bytes_img[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if bytes_img[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if bytes_img[:4] == b"GIF8":
        return ".gif"
    if bytes_img[:2] == b"BM":
        return ".bmp"
    return ".jpg"


def extrair_e_salvar(resposta, saida):
    """Extrai a imagem (base64) da resposta nativa NIM e salva em disco."""
    img_b64 = None
    semente = None

    if "artifacts" in resposta:  # formato nativo NIM
        artefato = resposta["artifacts"][0]
        img_b64 = artefato.get("base64")
        semente = artefato.get("seed")
        razao = artefato.get("finishReason")
        if razao == "ERROR":
            print("[erro] O modelo retornou ERROR (falha interna).")
            return False
        if razao == "CONTENT_FILTERED":
            print("[aviso] O filtro de conteudo alterou/barrou a imagem gerada.")
    elif "error" in resposta:  # mensagem de erro do gateway
        print(f"[erro] API retornou erro: {json.dumps(resposta['error'], ensure_ascii=False)[:400]}")
        return False

    if not img_b64:
        print("[erro] Nao foi possivel extrair a imagem da resposta da API.")
        return False

    bytes_img = base64.b64decode(img_b64)

    saida = Path(saida)
    if saida.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        saida = saida.with_suffix(detectar_extensao(bytes_img))
    elif saida.suffix.lower() == ".png" and detectar_extensao(bytes_img) == ".jpg":
        saida = saida.with_suffix(".jpg")  # o modelo devolve JPEG; evita .png falso

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_bytes(bytes_img)
    print(f"[ok] Imagem salva: {saida} ({len(bytes_img) // 1024} KB)")
    if semente is not None:
        print(f"[ok] Semente usada: {semente} (use --semente {semente} para reproduzir)")
    return True


# ----------------------------------------------------------------------------
# Comandos
# ----------------------------------------------------------------------------

def cmd_gerar(args):
    if args.teste:
        return _teste_offline(args)
    chave = obter_chave(args.chave)
    if not chave:
        sys.exit("[erro] Chave da API nao encontrada. Use --chave, a variavel NVIDIA_API_KEY ou crie ~/.nvidia_api_key")
    if args.salvar_chave:
        salvar_chave(chave)

    payload = {
        "prompt": args.prompt,
        "cfg_scale": args.escala,
        "seed": args.semente,
        "steps": args.passos,
        "width": args.largura,
        "height": args.altura,
    }

    url = f"{BASE_URL}/{MODELO}"
    print(f"[info] Gerando imagem com flux.1-dev ({args.largura}x{args.altura}, {args.passos} passos)...")
    resposta, erro = chamar_api(url, chave, payload)
    if erro:
        print(f"[erro] Falha na chamada a API (HTTP {erro[0]}): {erro[1]}")
        return False
    return extrair_e_salvar(resposta, args.saida)


def _teste_offline(args):
    """Testa o pipeline de salvamento sem rede, usando um JPEG 1x1."""
    print("[info] Modo teste offline (sem chamar a API).")
    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAEElEQVR4nGI4f/48AwAI/AP/3pS4WQAAAABJRU5ErkJggg=="
    )
    Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
    Path(args.saida).write_bytes(png_1x1)
    print(f"[ok] Teste OK. Arquivo de teste salvo: {args.saida}")
    return True


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="nvidia_imagem",
        description="Gera imagens com a API gratuita da NVIDIA NIM (flux.1-dev).",
        epilog="Exemplos:\n"
               "  python nvidia_imagem.py gerar \"um gato astronauta\" --saida gato.png\n"
               "  python nvidia_imagem.py gerar \"poster cyberpunk\" --largura 1344 --altura 768 --saida poster.png",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--chave", help="Chave da API NVIDIA (opcional se NVIDIA_API_KEY estiver definida)")
    parser.add_argument("--salvar-chave", action="store_true", help="Grava a chave em ~/.nvidia_api_key")
    parser.add_argument("--teste", action="store_true", help="Modo teste offline (nao chama a API)")

    sub = parser.add_subparsers(dest="comando", required=True)

    p_gerar = sub.add_parser("gerar", help="Gera uma imagem a partir de texto (flux.1-dev)")
    p_gerar.add_argument("prompt", help="Descricao da imagem desejada (max 10000 caracteres)")
    p_gerar.add_argument("--largura", type=int, default=1024,
                         help="Largura em pixels (768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280 ou 1344; padrao 1024)")
    p_gerar.add_argument("--altura", type=int, default=1024,
                         help="Altura em pixels (mesmos valores; padrao 1024)")
    p_gerar.add_argument("--passos", type=int, default=50, help="Passos de difusao (5-100; padrao 50)")
    p_gerar.add_argument("--escala", type=float, default=3.5, help="Aderencia ao prompt, cfg_scale (1-9; padrao 3.5)")
    p_gerar.add_argument("--semente", type=int, default=0, help="Semente para reproduzir (0 = aleatoria)")
    p_gerar.add_argument("--saida", default="imagem_gerada.png", help="Arquivo de saida (padrao imagem_gerada.png)")
    p_gerar.add_argument("--teste", action="store_true", help="Modo teste offline (nao chama a API)")

    args = parser.parse_args()

    # Validacoes de faixa
    if args.largura not in DIMENSOES_VALIDAS or args.altura not in DIMENSOES_VALIDAS:
        sys.exit(f"[erro] Largura/altura invalidas. Use: {', '.join(map(str, DIMENSOES_VALIDAS))}")
    if not (5 <= args.passos <= 100):
        sys.exit("[erro] --passos deve estar entre 5 e 100.")
    if not (1 < args.escala <= 9):
        sys.exit("[erro] --escala deve estar entre 1 e 9.")

    if len(args.prompt) > 10000:
        sys.exit("[erro] Prompt acima de 10000 caracteres.")

    cmd_gerar(args)


if __name__ == "__main__":
    main()
