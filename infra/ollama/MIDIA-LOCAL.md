# Imagens e narração locais em máquinas com pouca VRAM

O complemento `docker-compose.local-media.yml` usa SD-Turbo e Kokoro na CPU.
A GPU fica disponível para o modelo de texto no Ollama. A configuração AMD
original continua em `docker-compose.yml`.

## Instalação

Execute na raiz do projeto:

```sh
mkdir -p models/comfyui/checkpoints
curl -fL --retry 3 -o models/comfyui/checkpoints/sd_turbo.safetensors.part \
  https://huggingface.co/stabilityai/sd-turbo/resolve/main/sd_turbo.safetensors
mv models/comfyui/checkpoints/sd_turbo.safetensors.part \
  models/comfyui/checkpoints/sd_turbo.safetensors
```

No `.env`, selecione os arquivos e habilite a mídia:

```dotenv
COMPOSE_PROFILES=harness
COMPOSE_FILE=docker-compose.yml:docker-compose.ollama.yml:docker-compose.local-media.yml
IMAGE_ENABLED=true
VOICE_ENABLED=true
AUDIO_PROVIDER=openai
AUDIO_BASE_URL=http://gamentic-kokoro:8880
AUDIO_MODEL=kokoro
```

`openai` é o formato da API. A síntese ocorre no container local Kokoro,
sem chave e sem envio à OpenAI. O complemento define o modelo, as dimensões
das imagens e a rota de áudio do frontend.

```sh
docker compose build image image-api
docker compose up -d image image-api kokoro orchestrator frontend ollama-proxy
```

O serviço Maya original usa o perfil `maya` neste complemento e fica desativado.
O SD-Turbo usa resolução próxima de 512 pixels e um passo.
Os prompts internos de imagem são preparados em inglês. No complemento local,
`IMAGE_PROMPT_WORDS=36` separa estilo, aparência, roupa e iluminação para que o
estilo não ocupe todo o contexto curto do encoder. O enquadramento de cada vista
também é compacto (`IMAGE_COMPACT_PROMPTS=true`). Textos, legendas e narração
continuam em português. A aparência sem detalhes físicos exige inferência visual
do diretor de arte; o modelo leve não garante identidade entre vistas.
Ele não recebe as referências de identidade do workflow FLUX original;
a aparência entre imagens pode variar. Imagens na CPU levam mais tempo.

## Aventura criada com mídia desativada

Habilitar os serviços não gera retroativamente as imagens. Para recuperar uma
aventura, use as funções existentes `integrate.assign_voices_for_game`,
`integrate.reresolve_voices`, `integrate.generate_scene_image` e
`integrate.generate_images_for_game`, informando o ID correto e preservando
o banco. Elas reaproveitam imagens existentes e preenchem as ausentes.

Na interface, abra a engrenagem e ative **Áudio → Voz**. Para ouvir a história
automaticamente, ative também **Voz do narrador**. O botão de reprodução
ao lado de cada trecho permite ouvir manualmente.

## Fontes

- https://github.com/remsky/Kokoro-FastAPI
- https://huggingface.co/stabilityai/sd-turbo
- https://comfyanonymous.github.io/ComfyUI_examples/sdturbo/
