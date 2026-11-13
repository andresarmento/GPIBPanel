# GPIBPanel — Ideias para o futuro

Funcionalidades levantadas durante o desenvolvimento, ainda não agendadas.
O plano das fases fica em [FASES.md](FASES.md).

## Fontes

Recursos da **E3632A** ainda não expostos pelo driver (a maioria vale para outras
fontes também: o que for comum entra no contrato `PowerSupply`, o específico fica no driver).

- [ ] **Indicação CV/CC** (modo de regulação): ler `STAT:QUES:COND?` na leitura
      automática e mostrar um selo "CV"/"CC" ao lado do display.
      ⚠ Confirmar no hardware qual bit é CV e qual é CC (rodar `STAT:QUES:COND?`
      com a saída ligada sem carga → CV, e em curto/limite baixo → CC).
- [ ] **Proteções OVP/OCP**:
  - OVP: `VOLT:PROT <nível>`, `VOLT:PROT:STAT ON|OFF`
  - OCP: `CURR:PROT <nível>`, `CURR:PROT:STAT ON|OFF`
  - Ver se disparou: `VOLT:PROT:TRIP?` / `CURR:PROT:TRIP?`; rearmar: `VOLT:PROT:CLE` / `CURR:PROT:CLE`
  - Na tela: campos de nível + liga/desliga, alarme visível "OVP/OCP disparou" com botão rearmar.
  - Relaciona-se com o "estado seguro" da Fase 8.
- [ ] **Leitura mais rápida** (otimização do ciclo, hoje 6 consultas separadas):
  - `APPL?` devolve tensão e corrente programadas numa consulta só;
  - juntar consultas numa mensagem (`MEAS:VOLT?;:MEAS:CURR?`) para economizar idas e voltas no GPIB;
  - ler faixa/saída/valores programados com menos frequência que as medições
    (só mudam por comando — ou pelo painel frontal).
- [ ] **Mensagem no display da fonte**: `DISP:TEXT "SCRIPT RODANDO"` / `DISP:TEXT:CLE`
      (ex.: mostrar na bancada que um script está no controle — Fase 7).
- [ ] **Memórias de estado**: `*SAV 1..3` / `*RCL 1..3` como presets rápidos
      (ex.: "5 V / 1 A", "12 V / 0,5 A").
- [ ] **Trigger (mudança sincronizada)**: `VOLT:TRIG`, `CURR:TRIG`, `TRIG:SOUR BUS|IMM`,
      `TRIG:DEL`, `*TRG` — aplicar valores em várias fontes no mesmo instante (scripts, Fase 7).
- [ ] **Devolver ao painel frontal (LOCAL)**: botão que manda `++loc` pelo AR488 para
      destravar os botões da fonte sem desconectar (fica no transporte, não no driver).

## Multímetros

Recursos do **Keithley 2015** que ficaram fora da primeira versão (Fase 6):

- [ ] **Distorção**: THD, THD+N e SINAD (frequência fundamental, número de harmônicas, filtros).
- [ ] **Gerador interno** do 2015 (saída de sinal para medir distorção).
- [ ] Outras funções: temperatura, continuidade, diodo, período.
- [ ] Opções avançadas: filtro de média (tipo e contagem), autozero.

## Geradores de funções

Recursos do **HP 33120A** que ficaram fora da primeira versão (Fase 6):

- [ ] **Modulação**: AM, FM e FSK.
- [ ] **Varredura** (sweep) de frequência e **burst**.
- [ ] **Formas arbitrárias** (USER): escolher entre as gravadas no aparelho e enviar novas.
- [ ] Mensagem no display do aparelho (`DISP:TEXT`), como na fonte.

## Geradores de RF

Recursos do **Anritsu MG3601A** que ficaram fora da primeira versão (Fase 6):

- [ ] **Modulação**: AM, FM e ΦM, interna (400 Hz / 1 kHz / oscilador AF) ou externa.
- [ ] Offsets de frequência e de nível (`FO`, `LO`), memórias (`ST`/`RL`), passo ΔF.
- [ ] Mandar `SP01` (buzzer desligado) ao conectar, se o aparelho voltar a bipar depois de religado.
- [ ] Confirmar no aparelho: 0,0 dBm com RF ligado deve ser lido como ligado (`E-01`).

## Scripts

Planejamento da **Fase 7**: scripts em Python escritos na página e executados no servidor.

**Decidido (2026-11-13):**
- [x] **Nomes da API do script em inglês**: `equipment("...")`, `sleep(0.5)`, e os métodos
      do driver como já estão (`apply`, `set_voltage`, `measure`...). Exemplo:
      ```python
      psu = equipment("Fonte Agilent E3632A")
      psu.apply("OUT", range="P15V", voltage=0, current=0.5, output=True)
      for v in range(0, 13):
          psu.set_voltage("OUT", v)
          sleep(0.5)
          volts, amps = psu.measure("OUT")
          print(f"{v:2d} V -> {amps * 1000:.1f} mA")
      psu.set_output("OUT", False)
      ```
- [x] **Um script por vez** (mais simples e seguro: dois scripts na mesma fonte dariam confusão).

**Em aberto:**
- [ ] **Editor de código**: Monaco ou outro? Requisito: **não depender de internet**.
  - Monaco (o editor do VS Code) funciona offline se empacotado via npm junto com o
    frontend (sem CDN), mas acrescenta alguns MB.
  - Alternativa mais leve: CodeMirror 6 (também offline via npm, bem menor; colorização
    de Python e autocompletar possíveis).
  - Ou um `<textarea>` simples com fonte monoespaçada (zero dependência, sem cores/autocompletar).

**Proposta já apresentada (a confirmar junto com o editor):**
- Scripts salvos no SQLite (nome + código), lista ao lado do editor.
- Execução numa thread dentro do servidor; acesso ao barramento pela fila única;
  mesmos drivers e validações de limite; mudanças aparecem na hora nos painéis.
- Log ao vivo (`print`), erro com o número da linha, botão **parar** que interrompe
  na hora (inclusive dentro de `sleep()` e de laços).
- Desligar saídas automaticamente ao parar/dar erro → Fase 8 ("estado seguro").
