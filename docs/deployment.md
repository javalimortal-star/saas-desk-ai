# Publicação no Render

Escolha registrada em 13 de agosto de 2026: Render Blueprint. A plataforma foi escolhida porque oferece os quatro componentes do projeto no mesmo manifesto: web service para Django, PostgreSQL gerenciado, Key Value compatível com Redis e background worker para Celery.

Fontes oficiais: [Django no Render](https://render.com/docs/deploy-django), [background workers](https://render.com/docs/background-workers), [Blueprint](https://render.com/docs/blueprint-spec) e [variáveis secretas](https://render.com/docs/configure-environment-variables).

O processo web não é alcançável diretamente pela internet: todo tráfego entra pelo balanceador da plataforma. O marcador automático `RENDER=true` habilita a leitura defensiva do último endereço válido de `X-Forwarded-For`; prefixos forjados são ignorados. Fora do Render, somente endereços em `TRUSTED_PROXY_IPS` são confiados.

## Custo e criação

O worker contínuo não possui plano gratuito. O manifesto fixa web, PostgreSQL e Key Value no plano gratuito e o worker no plano `starter`; confirme o preço exibido pelo Render antes de aplicar o Blueprint.

1. No Render, crie um Blueprint a partir de `javalimortal-star/saas-desk-ai`.
2. Informe uma nova `OPENROUTER_API_KEY` quando o painel solicitar. Nunca grave a chave no Git. A senha intencionalmente pública da conta limitada é definida no manifesto para que avaliadores consigam entrar.
3. Confira os planos e aplique. Migrações rodam em `preDeployCommand`; `seed_demo` roda somente no primeiro deploy.
4. Guarde o URL externo em `README.md` e `docs/candidatura.md` após o smoke test.

## Verificação publicada

- `GET /health/` retorna `{"status":"ok"}`.
- O formulário público aceita somente dados fictícios e mostra um Protocolo sem dados privados.
- O worker conclui uma Análise assistida real ou registra Falha na análise sanitizada.
- `demo-analyst` entra sem acesso administrativo, revisa, trata manualmente e resolve.
- `/api/docs/` abre o Swagger; `/api/schema/` entrega o OpenAPI.
- Repetir uma análise respeita idempotência e limite de frequência.

Registre data, commit, URL e resultado de cada item antes de fechar a issue #11.

## Gravação segura

O arquivo `docs/demo.gif` registra o formulário fictício → Protocolo → login → fila → Análise assistida → edição humana → Resolução → Swagger. Ele usa somente dados fictícios e não mostra chave, cookie, DevTools ou painel de segredos. As imagens-fonte sanitizadas estão versionadas em `docs/demo-frames/`; após instalar as dependências de desenvolvimento, remonte o GIF com `python scripts/build_demo_gif.py`.
