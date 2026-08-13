# Publicação no Render

Escolha registrada em 13 de agosto de 2026: Render Blueprint. A plataforma é compatível com a arquitetura completa — web service para Django, PostgreSQL gerenciado, Key Value compatível com Redis e background worker para Celery —, mas o Blueprint de portfólio usa apenas os componentes gratuitos.

Fontes oficiais: [Django no Render](https://render.com/docs/deploy-django), [background workers](https://render.com/docs/background-workers), [Blueprint](https://render.com/docs/blueprint-spec) e [variáveis secretas](https://render.com/docs/configure-environment-variables).

O processo web não é alcançável diretamente pela internet: todo tráfego entra pelo balanceador da plataforma. O marcador automático `RENDER=true` habilita a leitura defensiva do último endereço válido de `X-Forwarded-For`; prefixos forjados são ignorados. Fora do Render, somente endereços em `TRUSTED_PROXY_IPS` são confiados.

## Diferença intencional da demonstração

O worker contínuo não possui plano gratuito. Para evitar cobrança, `render.yaml` cria somente Django e PostgreSQL gratuitos e configura `CELERY_TASK_ALWAYS_EAGER=true`. A Análise assistida usa a integração real com OpenRouter, mas roda no processo da requisição. Redis e o worker separado permanecem no Docker Compose e são o desenho recomendado para uma produção com carga real.

Essa diferença é explícita e limitada ao ambiente gratuito. Não existe fallback automático para o provedor falso.

## Custo e criação

O manifesto fixa todos os recursos criados no plano `free`. O PostgreSQL gratuito expira após 30 dias e a aplicação web pode hibernar depois de ficar ociosa, conforme a [documentação do plano gratuito](https://render.com/docs/free).

1. No Render, crie um Blueprint a partir de `javalimortal-star/saas-desk-ai`.
2. Informe uma nova `OPENROUTER_API_KEY` quando o painel solicitar. Nunca grave a chave no Git. A senha intencionalmente pública da conta limitada é definida no manifesto para que avaliadores consigam entrar.
3. Confira que web e PostgreSQL estão como `free` e aplique. Como `preDeployCommand` é pago, o comando de inicialização executa migrações e `bootstrap_demo` antes do Gunicorn. Esse bootstrap cria somente fixtures ausentes e preserva revisões e senhas existentes após uma retomada do serviço.
4. Guarde o URL externo em `README.md` e `docs/candidatura.md` após o smoke test.

## Verificação publicada

- `GET /health/` retorna `{"status":"ok"}`.
- O formulário público aceita somente dados fictícios e mostra um Protocolo sem dados privados.
- O modo eager conclui uma Análise assistida real ou registra Falha na análise sanitizada; nenhuma resposta `fake` é usada.
- `demo-analyst` entra sem acesso administrativo, revisa, trata manualmente e resolve.
- `/api/docs/` abre o Swagger; `/api/schema/` entrega o OpenAPI.
- Repetir uma análise respeita idempotência e limite de frequência.

Registre data, commit, URL e resultado de cada item antes de fechar a issue #11.

### Resultado do smoke test

Verificado em 13 de agosto de 2026 no commit `da340b5`, em <https://saas-desk-ai-web.onrender.com/>:

O avaliador entra em <https://saas-desk-ai-web.onrender.com/analyst/login/> com `demo-analyst` / `demo-password`; a conta não é `staff` nem superusuária.

- health check, Swagger e esquema OpenAPI responderam com sucesso;
- o formulário retornou somente o Protocolo para dados fictícios;
- a primeira tentativa indisponível foi registrada com mensagem sanitizada e a repetição concluiu com o modelo gratuito real `google/gemma-4-26b-a4b-it:free`;
- o Analista editou a Resposta sugerida e resolveu a Solicitação;
- uma fixture com falha foi classificada e resolvida manualmente, sem depender da IA;
- a conta demonstrativa permaneceu sem acesso administrativo e a API do Analista recusou acesso anônimo.

## Gravação segura

O arquivo `docs/demo.gif` registra o formulário fictício → Protocolo → login → fila → Análise assistida → edição humana → Resolução → Swagger. Ele usa somente dados fictícios e não mostra chave, cookie, DevTools ou painel de segredos. As imagens-fonte sanitizadas estão versionadas em `docs/demo-frames/`; após instalar as dependências de desenvolvimento, remonte o GIF com `python scripts/build_demo_gif.py`.
