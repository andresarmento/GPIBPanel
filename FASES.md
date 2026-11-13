# GPIBPanel — Fases do projeto

Trabalho dividido em fases pequenas. Cada fase só começa depois que a anterior
foi testada e validada.

| # | Fase | Status |
|---|------|--------|
| 0 | Estrutura do projeto | ✅ concluída |
| 1 | Transporte AR488 + simulado | ✅ concluída (validada no hardware real) |
| 2 | Drivers | ✅ concluída (validada no hardware real) |
| 3 | Cadastro de equipamentos | ✅ concluída |
| 4 | Controle em tempo real | ✅ concluída (validada no hardware real) |
| 5 | Painéis | ✅ concluída |
| 6 | Scripts | ⏳ próxima |
| 7 | Acabamento | — |

---

## Fase 0 — Estrutura ✅

- Backend FastAPI (uvicorn) e frontend Svelte 5 + Vite + Tailwind.
- Endpoint `/api/health` e página mostrando o status do backend.
- Proxy do Vite repassando `/api` para o backend em desenvolvimento.

**Pronto quando:** a página em http://localhost:5173 mostra "Backend: ok".

## Fase 1 — Transporte AR488 + simulado ✅

- Interface comum de transporte (write / read / query).
- Transporte **AR488** pela serial (protocolo Prologix).
- Transporte **simulado** com uma E3632A virtual no endereço 5.
- **Fila única** do barramento: todo acesso passa por uma só thread, em ordem.
- API para conectar/desconectar, listar portas e mandar comandos.
- Tela com painel de conexão e console GPIB.

**Pronto quando:** `*IDN?` na E3632A real responde `HEWLETT-PACKARD,E3632A,...`.

## Fase 2 — Drivers ✅

- Tipo de equipamento **PowerSupply**: contrato comum a qualquer fonte
  (canais, tensão, corrente, saída liga/desliga, medições).
- Driver **E3632A**: 1 saída, faixas P15V (15 V / 7 A) e P30V (30 V / 4 A);
  valida limites e verifica erros do instrumento (`SYST:ERR?`).
- Identificação automática do driver pela resposta do `*IDN?`.
- Detalhes do modelo ficam só dentro do driver.
- Validação de limites e ordem segura (desliga saída → faixa → corrente → tensão → liga saída)
  ficam no tipo PowerSupply, iguais para qualquer fonte.
- Tela provisória **Teste de driver** (identificar, ler, ajustar, ligar/desligar).

**Pronto quando:** na E3632A real, "identificar" mostra o driver E3632A; ajustar
tensão/corrente, trocar a faixa e ligar a saída funciona e as medições batem com o
display da fonte; um valor fora da faixa (ex.: 20 V em P15V) é recusado sem enviar nada.

## Fase 3 — Cadastro de equipamentos ✅

- CRUD de equipamentos (nome, endereço GPIB, driver, observações, foto) salvo em SQLite
  (`backend/data/gpibpanel.db`; a foto fica dentro do banco).
- Nome único (sem diferenciar maiúsculas). Endereço repetido é permitido, mas marcado com ⚠.
- Foto: PNG, JPEG, GIF ou WEBP, até 5 MB (o tipo é conferido pelo conteúdo do arquivo).
- **Detectar** no formulário: pergunta `*IDN?` no endereço e escolhe o driver.
- **Verificar** no card: confere se o equipamento responde e se o modelo bate com o driver.
- Tela organizada em abas.

**Pronto quando:** cadastrar a E3632A com foto (usando "detectar"), editar, ver
"online" ao verificar, reiniciar o backend e o cadastro continuar lá; excluir funciona.

## Fase 4 — Controle em tempo real ✅

- Leituras ao vivo via WebSocket (`/api/ws`): o backend lê só os equipamentos que
  alguma tela está mostrando (aba do navegador escondida = para de ler).
- **Intervalo de leitura por equipamento**, salvo no cadastro: 250 ms, 500 ms, 1 s,
  2 s, 5 s ou pausado. A tela mostra quanto cada leitura realmente leva e avisa
  quando é mais lenta que o intervalo.
- Componente **canal de fonte**: display de V/A medidos, faixa, tensão, corrente
  (Enter aplica, Esc desfaz; campos pendentes ficam destacados) e liga/desliga.
- Comandos pelo equipamento cadastrado (usa o driver salvo); depois de um comando a
  tela atualiza na hora.
- Instrumento sem resposta / barramento desconectado aparecem no status, sem travar.
- Aba **Controle** substitui a provisória "Teste de driver".

**Pronto quando:** na aba Controle a E3632A atualiza sozinha; mudar o intervalo muda
o ritmo (e fica salvo após recarregar); ajustar V/I/faixa e ligar/desligar reflete na
hora; com duas abas do navegador abertas, as duas mostram o mesmo; desligar o cabo/
fonte mostra "sem resposta" e volta sozinho ao religar.

## Fase 5 — Painéis ✅

- Vários painéis com nome, salvos no SQLite (tabela `panels`, widgets em JSON).
- Grade de 12 colunas: no modo **editar**, arrastar move, o canto inferior direito
  redimensiona, encaixa nas células e não deixa sobrepor; ⚙ configura, ✕ remove.
  Mudanças só valem ao **salvar** (cancelar descarta).
- Widgets: **Canal de fonte** (completo), **Display** (V, A, W = V×A, ou valores
  programados; casas decimais configuráveis), **Botão de saída**, **Texto** e
  **Gráfico** (uma grandeza por gráfico, janela de 1/5/15/30 min, valor sob o mouse).
- O gráfico usa só o histórico em memória desde que a página abriu.
- Vários widgets do mesmo equipamento compartilham uma leitura só (intervalo do cadastro).
- **Tela cheia** para monitor de bancada; o último painel aberto é lembrado.

**Pronto quando:** criar um painel com os 5 tipos de widget para a E3632A, arrumar
na grade, salvar, recarregar a página e ele voltar igual; controles e gráfico
funcionando ao vivo; tela cheia ok; editar → cancelar descarta as mudanças.

## Fase 6 — Scripts

- Scripts em Python rodando no servidor, com editor Monaco, log ao vivo e botão de parar.

## Fase 7 — Acabamento

- Estado seguro (desligar saídas em erro/encerramento), exportação CSV,
  empacotamento (FastAPI servindo o frontend compilado, um servidor só).
- **Histórico das leituras** guardado no backend (o gráfico da Fase 5 só tem o que
  chegou desde que a página abriu) e exportação dos dados do gráfico em **CSV**.
