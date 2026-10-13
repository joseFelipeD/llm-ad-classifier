# Guia prático — orquestração de IA para o desafio

## Pastas do projeto
Crie um projeto `classificador-anuncios` contendo o README original, `evaluate.py`, `data/train.jsonl` e `data/test_unlabeled.jsonl`. Extraia o conteúdo deste pacote **na raiz do projeto**, sem apagar nem sobrescrever o README/dados do desafio. Este pacote adiciona instruções, agentes, skill e prompts; ele **não** implementa o desafio.

## Windows PowerShell: ferramentas
Instale Git for Windows, Python 3.11+ e VS Code a partir de fontes oficiais e confira `git --version`, `py --version`, `code --version`.
Para o Claude Code: `irm https://claude.ai/install.ps1 | iex`, depois abra um novo terminal e execute `claude --version`, `claude doctor` e `claude`. Entre usando a assinatura Claude Pro, e **não** com chave API por engano.
Para o Codex: no app ChatGPT desktop Windows, escolha Codex e abra o mesmo repositório, entrando com ChatGPT Plus. Alternativa: CLI Codex, instalação via npm se Node.js estiver disponível (`npm install -g @openai/codex`) e `codex` para login. Configure modo de leitura/revisão sem escrita/execução externa.
No Gemini web (`https://gemini.google.com`), vá a Gems > Novo Gem e cole `prompts/06_gemini_gem_instrucoes.md`. Adicione README, train e evaluate.py como conhecimento, caso suportados, sem credenciais.

## Git e estrutura
Inicialize Git depois que os arquivos estiverem na pasta, confira `git status`, crie `.gitignore` para `.env`, `.venv`, `__pycache__`, `.pytest_cache`, arquivos temporários e `.claude/settings.local.json`. **Não** ignore o `predictions.jsonl` e o `usage.json` finais. Preserve histórico de commits sem squash. Na finalização, mantenha o enunciado original (por exemplo `git mv README.md ENUNCIADO_ORIGINAL.md`) e crie um `README.md` da solução com os comandos de instalação/execução; ajuste referências no projeto a esses nomes. Não faça essa troca antes da primeira análise, que procura o enunciado original no README.

## Plugins
Claude Code: execute `/plugin`, navegue pelo marketplace oficial e considere o `commit-commands`; use apenas com autorização de commit. Ou no terminal `claude plugin install commit-commands@claude-plugins-official --scope user`. Confira `/plugin` > Installed e `claude plugin list`. Plugins têm permissões e podem incluir hooks/MCP; inspecione a descrição antes de instalar.
ChatGPT/Codex: plugin GitHub é opcional; conecte pela seção Plugins do ChatGPT após revisar as permissões. Não é obrigatório para execução local. Se usar Codex CLI, `/plugins` abre navegador de plugins; não é preciso instalar plugins de desenvolvimento para a revisão do repositório.
Claude Code: já inclui dois subagentes locais definidos em `.claude/agents/` e uma skill `/auditar-entrega`. Para validar, inicie Claude na raiz e peça que liste agentes ou delegue uma inspeção; se foi criada nova pasta com a sessão aberta, reinicie a sessão.

## Ordem dos prompts
1. Claude Code: `prompts/01_claude_diagnostico.md`. Aguarde plano e aprove.
2. Gemini Gem: `prompts/07_gemini_analise.md` com plano do Claude. Use recomendações como hipóteses.
3. Claude Code: `prompts/02_claude_baseline.md` com decisões aprovadas.
4. Codex: `prompts/05_codex_revisao.md`, sem alterar arquivos. Analise as correções com Claude.
5. Claude Code: `prompts/03_claude_experimentos.md`. Aprove consumo de API.
6. Codex: `prompts/08_codex_segunda_passada.md` para revisar alterações.
7. Claude Code: `prompts/04_claude_finalizacao.md` e `/auditar-entrega`, após sua autorização.

## Credenciais
Obtenha chave própria de API gratuita ou paga; verifique cotas atuais, disponibilidade de modelo e metadados `usage`. Configure `.env` ou variável de ambiente conforme o projeto implementado. Não coloque chaves em prompts, logs ou arquivos versionados.

## Atenção
Claude Pro, ChatGPT Plus e Gemini Plus são assinaturas de produtos de assistência; o acesso à API de classificação é uma configuração à parte. Não compartilhe a mesma pasta com dois agentes escrevendo simultaneamente. README original e evaluate.py devem ser preservados.
