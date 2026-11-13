# GPIBPanel — Fases do projeto

Trabalho dividido em fases pequenas. Cada fase só começa depois que a anterior
foi testada e validada.

| # | Fase | Status |
|---|------|--------|
| 0 | Estrutura do projeto | ✅ concluída |
| 1 | Transporte AR488 + simulado | ✅ concluída (validada no hardware real) |
| 2 | Drivers | ✅ concluída (validada no hardware real) |
| 3 | Cadastro de equipamentos | 🧪 implementada, aguardando validação |
| 4 | Controle em tempo real | — |
| 5 | Painéis | — |
| 6 | Scripts | — |
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

## Fase 3 — Cadastro de equipamentos 🧪

- CRUD de equipamentos (nome, endereço GPIB, driver, observações, foto) salvo em SQLite
  (`backend/data/gpibpanel.db`; a foto fica dentro do banco).
- Nome único (sem diferenciar maiúsculas). Endereço repetido é permitido, mas marcado com ⚠.
- Foto: PNG, JPEG, GIF ou WEBP, até 5 MB (o tipo é conferido pelo conteúdo do arquivo).
- **Detectar** no formulário: pergunta `*IDN?` no endereço e escolhe o driver.
- **Verificar** no card: confere se o equipamento responde e se o modelo bate com o driver.
- Tela organizada em abas: Equipamentos · Teste de driver · Console GPIB.

**Pronto quando:** cadastrar a E3632A com foto (usando "detectar"), editar, ver
"online" ao verificar, reiniciar o backend e o cadastro continuar lá; excluir funciona.

## Fase 4 — Controle em tempo real

- Leituras de tensão/corrente atualizando ao vivo via WebSocket.
- Componente de canal de fonte (ajuste, liga/desliga, faixa).
- Atualização automática das leituras (sem botão "ler"), com o **intervalo de leitura
  configurável** pelo usuário (ex.: 250 ms, 500 ms, 1 s, 2 s, pausado).

## Fase 5 — Painéis

- Editor de painéis em grade: montar telas com os controles dos equipamentos.

## Fase 6 — Scripts

- Scripts em Python rodando no servidor, com editor Monaco, log ao vivo e botão de parar.

## Fase 7 — Acabamento

- Estado seguro (desligar saídas em erro/encerramento), exportação CSV,
  empacotamento (FastAPI servindo o frontend compilado, um servidor só).
