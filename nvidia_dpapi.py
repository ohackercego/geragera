#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Armazenamento criptografado da chave da API NVIDIA (somente biblioteca padrao).

Windows: usa DPAPI (CryptProtectData do crypt32.dll) - a chave fica
criptografada e so pode ser decifrada pelo MESMO usuario na MESMA maquina.
Nada de segredo embutido no programa: o proprio Windows gerencia.

Outros sistemas (Linux/macOS): fallback de ofuscacao (XOR + base64).
Atencao: nesse fallback NAO e criptografia forte - apenas esconde a chave
de uma olhada casual. Para seguranca real nesses sistemas, use Windows.

Arquivo usado: ~/.nvidia_api_key.enc
Formato: "NVENC1:" + base64(dados criptografados)
"""

import base64
import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path

ARQUIVO_CHAVE_ENC = Path.home() / ".nvidia_api_key.enc"
MAGICO = b"NVENC1:"

# ----------------------------------------------------------------------------
# DPAPI (Windows)
# ----------------------------------------------------------------------------

class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _dpapi(proteger, dados):
    """Aplica CryptProtectData (proteger=True) ou CryptUnprotectData."""
    buf = ctypes.create_string_buffer(dados, len(dados))
    entrada = _DATA_BLOB(len(dados), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    saida = _DATA_BLOB()
    func = ctypes.windll.crypt32.CryptProtectData if proteger else ctypes.windll.crypt32.CryptUnprotectData
    if not func(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(saida)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(saida.pbData)


def _proteger_dpapi(dados):
    return _dpapi(True, dados)


def _desproteger_dpapi(dados):
    return _dpapi(False, dados)


# ----------------------------------------------------------------------------
# Fallback (nao-Windows): ofuscacao XOR
# ----------------------------------------------------------------------------

def _semente_maquina():
    """Chave de ofuscacao derivada do usuario/maquina (nao armazenada)."""
    base = os.environ.get("COMPUTERNAME", "") + os.environ.get("USERNAME", "") + os.path.expanduser("~")
    semente = 0
    for c in base.encode("utf-8"):
        semente = (semente * 31 + c) & 0xFFFFFFFF
    return semente & 0xFF


def _proteger_xor(dados):
    s = _semente_maquina()
    return bytes(b ^ s for b in dados)


def _desproteger_xor(dados):
    return _proteger_xor(dados)  # XOR e simetrico


# ----------------------------------------------------------------------------
# API publica
# ----------------------------------------------------------------------------

def proteger(chave):
    """Criptografa a chave (string) e devolve bytes no formato NVENC1."""
    dados = chave.encode("utf-8")
    if os.name == "nt":
        corpo = _proteger_dpapi(dados)
    else:
        corpo = _proteger_xor(dados)
    return MAGICO + base64.b64encode(corpo)


def desproteger(conteudo):
    """Decifra bytes NVENC1 e devolve a chave (string). None se invalido."""
    if not conteudo.startswith(MAGICO):
        return None
    try:
        corpo = base64.b64decode(conteudo[len(MAGICO):])
        if os.name == "nt":
            dados = _desproteger_dpapi(corpo)
        else:
            dados = _desproteger_xor(corpo)
        return dados.decode("utf-8")
    except Exception:
        return None


def ler_chave_salva():
    """Devolve a chave criptografada salva, ou None."""
    try:
        if ARQUIVO_CHAVE_ENC.exists():
            return desproteger(ARQUIVO_CHAVE_ENC.read_bytes())
    except Exception:
        pass
    return None


def salvar_chave_criptografada(chave):
    """Salva a chave criptografada em ~/.nvidia_api_key.enc."""
    chave = chave.strip()
    if not chave:
        return False
    ARQUIVO_CHAVE_ENC.write_bytes(proteger(chave))
    if os.name != "nt":
        try:
            os.chmod(ARQUIVO_CHAVE_ENC, 0o600)
        except Exception:
            pass
    return True


def chave_esta_salva():
    """True se existe uma chave criptografada valida salva."""
    return bool(ler_chave_salva())


if __name__ == "__main__":
    # Auto-teste: criptografa, decifra e confere
    chave_teste = "nvapi-teste-12345"
    blob = proteger(chave_teste)
    print(f"[ok] Protegido: {len(blob)} bytes (formato {blob[:7].decode()})")
    recuperada = desproteger(blob)
    print(f"[ok] Recuperada: {recuperada}")
    print(f"[{'ok' if recuperada == chave_teste else 'ERRO'}] Teste de ida-e-volta")
