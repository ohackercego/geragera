# Gerador de Imagens NVIDIA / NVIDIA Image Generator

Gerador e editor de imagens usando a API gratuita da NVIDIA (build.nvidia.com / NIM). Inclui interface web, linha de comando e executável único para Windows. 100% biblioteca padrão do Python (sem dependências).

Image generator and editor using NVIDIA's free API (build.nvidia.com / NIM). Includes a web interface, command line and a single Windows executable. 100% Python standard library (no dependencies).

---

## Português

### O que é

Programa que gera imagens a partir de texto usando a API gratuita da NVIDIA. Funciona de três formas:

- **Executável único (Windows)**: `dist/nvidia_imagem.exe` - basta executar e abrir o navegador.
- **App web (Python)**: `nvidia_imagem_web.py` - servidor local com página onde você digita a chave da API e o prompt.
- **Linha de comando**: `nvidia_imagem.py` - para automatizar e usar em scripts.

### Modelos usados

Verificado em 09/08/2026 com chave real:

| Modo | Modelo | Endpoint |
|---|---|---|
| Gerar imagem | `black-forest-labs/flux.1-dev` | `https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev` |

**Observação importante**: os modelos `qwen-image` e `qwen-image-edit` (Alibaba) aparecem no build.nvidia.com como "Downloadable" (self-host), ou seja, **não possuem endpoint hospedado gratuito** - qualquer chamada retorna 404. Por isso este projeto usa o flux.1-dev, o único modelo de imagem com endpoint gratuito funcional para geração.

### Requisitos

- Python 3.9 ou superior (apenas biblioteca padrão, não é preciso instalar nada)
- Conta gratuita e chave da API NVIDIA em https://build.nvidia.com (botão "Get API Key")

### Chave da API

A chave e pedida **uma unica vez**. Na primeira vez, o programa salva a chave **criptografada** (DPAPI do Windows - so o mesmo usuario, na mesma maquina, consegue decifrar) em `~/.nvidia_api_key.enc`. Nas proximas vezes a chave nao e pedida de novo; para trocar, use o link "Trocar chave" na pagina.

Ordem de busca da chave:

1. Argumento `--chave` (CLI) ou campo "Chave da API" (web, primeira vez)
2. Chave criptografada salva em `~/.nvidia_api_key.enc`
3. Variavel de ambiente `NVIDIA_API_KEY`
4. Arquivo antigo `~/.nvidia_api_key` (uma linha com a chave)

Na interface web, a chave digitada e usada apenas naquela requisicao - **nunca aparece em logs**.

### Como usar

#### Executável único (Windows)

1. Execute `nvidia_imagem.exe`
2. Abra no navegador: `http://localhost:8000`
3. Na primeira vez, digite a chave da API e clique em "Salvar chave criptografada" (depois disso a chave não é mais pedida)
4. Escreva o prompt e clique em "Gerar imagem"
5. A imagem aparece na página com o link "Baixar imagem" (a imagem também é salva em `saidas/`)
6. Para parar: feche a janela do terminal (ou Ctrl+C)

Para usar outra porta: `nvidia_imagem.exe --porta 9000`

#### App web (Python)

```bash
python nvidia_imagem_web.py            # porta 8000
python nvidia_imagem_web.py --porta 9000
```

Depois abra `http://localhost:8000` no navegador.

#### Linha de comando

```bash
# Gerar imagem
python nvidia_imagem.py gerar "um gato astronauta flutuando no espaco, estilo cartoon" --saida gato.png

# Gerar com parametros (largura/altura validas: 768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280 ou 1344)
python nvidia_imagem.py gerar "poster cyberpunk de cidade futurista" --largura 1344 --altura 768 --passos 40 --escala 5 --saida poster.png

# Teste offline (sem chave, sem gastar credito)
python nvidia_imagem.py gerar "teste" --teste --saida teste.png
```

### Limitações (tier gratuito)

- Dimensões de saída limitadas ao conjunto: 768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280 ou 1344.

### Como gerar o executável (build)

```bash
# Crie um ambiente virtual com Python 3.12 e instale o PyInstaller
python -m venv _build_venv
_build_venv/Scripts/pip install pyinstaller

# Empacote (gera dist/nvidia_imagem.exe)
_build_venv/Scripts/pyinstaller --onefile --name nvidia_imagem --distpath dist --workpath build --specpath . nvidia_imagem_web.py
```

### Estrutura do projeto

```
qwen-image-app/
├── nvidia_imagem.py        # CLI (linha de comando)
├── nvidia_imagem_web.py    # Servidor web (http.server, sem dependencias)
├── nvidia_dpapi.py         # Criptografia da chave (DPAPI do Windows)
├── README.md               # Este arquivo
└── dist/
    └── nvidia_imagem.exe   # Executável único (Windows)
```

---

## English

### What it is

A program that generates images from text using NVIDIA's free API. Three ways to use it:

- **Single executable (Windows)**: `dist/nvidia_imagem.exe` - just run it and open the browser.
- **Web app (Python)**: `nvidia_imagem_web.py` - local server with a page where you type your API key and the prompt.
- **Command line**: `nvidia_imagem.py` - for automation and scripting.

### Models used

Verified on 2026-08-09 with a real key:

| Mode | Model | Endpoint |
|---|---|---|
| Generate | `black-forest-labs/flux.1-dev` | `https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev` |

**Important note**: the `qwen-image` and `qwen-image-edit` models (Alibaba) are listed as "Downloadable" (self-host) on build.nvidia.com, meaning they **have no free hosted endpoint** - any API call returns 404. This project therefore uses flux.1-dev, the only image model with a working free endpoint for generation.

### Requirements

- Python 3.9+ (standard library only, nothing to install)
- Free NVIDIA account and API key from https://build.nvidia.com ("Get API Key" button)

### API key

The key is asked **only once**. On the first run, the program saves the key **encrypted** (Windows DPAPI - only the same user, on the same machine, can decrypt it) to `~/.nvidia_api_key.enc`. After that the key is not asked again; use the "Trocar chave" (change key) link on the page to replace it.

Key lookup order:

1. `--chave` argument (CLI) or "API key" field (web, first time)
2. Encrypted key saved in `~/.nvidia_api_key.enc`
3. `NVIDIA_API_KEY` environment variable
4. Legacy `~/.nvidia_api_key` file (single line with the key)

In the web interface, the typed key is used only for that request - **never shown in logs**.

### Usage

#### Single executable (Windows)

1. Run `dist/nvidia_imagem.exe`
2. Open the browser at: `http://localhost:8000`
3. On the first run, type your API key and click "Salvar chave criptografada" (the key is not asked again afterwards)
4. Type the prompt and click "Generate image" (Gerar imagem)
5. The image appears on the page with the "Baixar imagem" (download) link; it is also saved to `saidas/`
6. To stop: close the terminal window (or Ctrl+C)

To use another port: `nvidia_imagem.exe --porta 9000`

#### Web app (Python)

```bash
python nvidia_imagem_web.py            # port 8000
python nvidia_imagem_web.py --porta 9000
```

Then open `http://localhost:8000` in your browser.

#### Command line

```bash
# Generate an image
python nvidia_imagem.py gerar "a cat astronaut floating in space, cartoon style" --saida gato.png

# Generate with parameters (valid widths/heights: 768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280 or 1344)
python nvidia_imagem.py gerar "cyberpunk poster of a futuristic city" --largura 1344 --altura 768 --passos 40 --escala 5 --saida poster.png

# Offline test (no key, no credits used)
python nvidia_imagem.py gerar "test" --teste --saida teste.png
```

### Limitations (free tier)

- Output dimensions limited to: 768, 832, 896, 960, 1024, 1088, 1152, 1216, 1280 or 1344.

### How to build the executable

```bash
# Create a virtual environment with Python 3.12 and install PyInstaller
python -m venv _build_venv
_build_venv/Scripts/pip install pyinstaller

# Package (generates dist/nvidia_imagem.exe)
_build_venv/Scripts/pyinstaller --onefile --name nvidia_imagem --distpath dist --workpath build --specpath . nvidia_imagem_web.py
```

### Project structure

```
qwen-image-app/
├── nvidia_imagem.py        # CLI (command line)
├── nvidia_imagem_web.py    # Web server (http.server, no dependencies)
├── nvidia_dpapi.py         # Key encryption (Windows DPAPI)
├── README.md               # This file
└── dist/
    └── nvidia_imagem.exe   # Single executable (Windows)
```

---

## Licença / License

Projeto pessoal. Use livremente, sem garantias.
Personal project. Use freely, no warranties.
