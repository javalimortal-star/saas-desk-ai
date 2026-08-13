# SaaS Desk AI

Este contexto representa o recebimento e o tratamento assistido de solicitações de atendimento. A inteligência artificial apoia a análise, mas a decisão final permanece com uma pessoa.

## Language

**Solicitante**:
Pessoa que pede ajuda enviando uma solicitação pelo formulário público.
_Avoid_: Cliente, usuário final, requerente

**Analista**:
Pessoa responsável por tratar solicitações e realizar a revisão humana das recomendações recebidas.
_Avoid_: Atendente, operador, administrador

**Solicitação**:
Mensagem enviada por alguém que precisa de atendimento e que será acompanhada até sua resolução.
_Avoid_: Ticket, chamado, demanda

**Etapa da Solicitação**:
Momento atual de uma solicitação no ciclo Recebida, Em análise, Aguardando revisão, Falha na análise ou Resolvida.
_Avoid_: Status, situação, fase livre

**Protocolo**:
Código público e não sequencial que confirma o recebimento de uma solicitação sem revelar seu identificador interno ou conteúdo.
_Avoid_: ID, número do banco, código de acesso

**Análise assistida**:
Conjunto de recomendações produzidas por inteligência artificial para ajudar no tratamento de uma solicitação.
_Avoid_: Resposta da IA, decisão automática

**Tentativa de análise**:
Registro de uma execução da inteligência artificial, bem-sucedida ou não, preservado para comparação e histórico.
_Avoid_: Versão, requisição à API, log

**Categoria**:
Classificação do assunto de uma solicitação como Acesso, Cobrança, Problema técnico, Dúvida sobre funcionalidade ou Outro.
_Avoid_: Etiqueta, tag, assunto livre

**Prioridade**:
Indicação do impacto de uma solicitação como Baixa, Normal ou Alta, utilizada para orientar a ordem de tratamento.
_Avoid_: Urgência, severidade, pontuação

**Resposta sugerida**:
Texto recomendado como parte de uma análise assistida, ainda sujeito à revisão humana.
_Avoid_: Resposta automática, resposta final

**Resposta aprovada**:
Texto aceito pelo Analista como resultado final do atendimento, possivelmente após editar uma resposta sugerida.
_Avoid_: Resposta da IA, resposta enviada

**Revisão humana**:
Avaliação obrigatória da análise assistida antes que uma resposta seja considerada aprovada.
_Avoid_: Moderação, validação automática

**Resolução**:
Encerramento de uma solicitação após o registro de uma resposta aprovada.
_Avoid_: Envio, fechamento automático

**Falha na análise**:
Resultado de uma tentativa de produzir uma análise assistida que não pôde ser concluída, sem perda da solicitação original.
_Avoid_: Solicitação com erro, solicitação inválida

**Tratamento manual**:
Tratamento de uma solicitação realizado pelo Analista sem depender de uma análise assistida bem-sucedida.
_Avoid_: Resposta falsa, simulação de IA, fallback automático
