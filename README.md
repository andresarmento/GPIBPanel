# GPIBPanel

Painel web local para controlar instrumentos GPIB (via adaptador AR488).

- **backend/**: FastAPI (Python)
- **frontend/**: Svelte 5 + Vite + Tailwind

Plano e andamento: [FASES.md](FASES.md) · Ideias para o futuro: [TODO.md](TODO.md)

## Rodando em desenvolvimento

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Teste: http://127.0.0.1:8000/api/health → `{"status":"ok",...}`
Testes automáticos: `.venv\Scripts\python -m pytest`

### Frontend (precisa de Node.js 20+)

```powershell
cd frontend
npm install
npm run dev
```

Abra http://localhost:5173. O Vite repassa `/api` para o backend na porta 8000.

## Barramento GPIB

- `backend/app/gpib/`: transportes **AR488** (serial, protocolo Prologix) e **Simulado**
  (E3632A virtual no endereço 5, com carga de 10 Ω), e a **fila única** (`bus.py`):
  todo acesso ao barramento passa por uma só thread, em ordem.
- API: `GET /api/bus`, `GET /api/bus/ports`, `POST /api/bus/connect`
  (`{"kind":"sim"}` ou `{"kind":"ar488","port":"COM3"}`), `POST /api/bus/disconnect`,
  `POST /api/bus/write` e `POST /api/bus/query` (`{"address":5,"command":"*IDN?"}`).
- Na tela: painel **Conexão** e **Console GPIB** para mandar comandos SCPI.

## Drivers

- `backend/app/drivers/`: `base.py` (Instrument, InstrumentIO, SYST:ERR?), `power_supply.py`
  (contrato **PowerSupply**: canais, faixas, limites, ordem segura) e `e3632a.py` (driver).
  O driver é escolhido pelo modelo no `*IDN?` (`DRIVERS` em `drivers/__init__.py`).
- Drivers são síncronos e rodam dentro da fila do barramento (`bus.transaction`).
- API: `GET /api/drivers` e `POST /api/instruments/{addr}/identify` (*IDN? + driver reconhecido).

## Equipamentos

- Banco SQLite em `backend/data/gpibpanel.db` (criado sozinho; a pasta pode ser trocada
  pela variável de ambiente `GPIBPANEL_DATA`). Mudanças de estrutura: `MIGRATIONS` em `app/db.py`.
- API: `GET/POST /api/equipment`, `GET/PUT/DELETE /api/equipment/{id}`,
  `GET/PUT/DELETE /api/equipment/{id}/image` (upload multipart no campo `file`) e
  `POST /api/equipment/{id}/check` (responde? o modelo bate com o driver?).

## Tempo real

- `backend/app/live.py`: um leitor por equipamento observado chama `driver.snapshot()`
  pela fila do barramento, no intervalo `poll_ms` do cadastro (0 = pausado).
- WebSocket `/api/ws`: a tela manda `{"subscribe": [ids]}` e recebe
  `{"type":"state","id":1,"ok":true,"status":"ok","data":{...},"poll_ms":1000,"cycle_ms":180,...}`.
- `POST /api/equipment/{id}/psu/{canal}` (`{"range":"P30V","voltage":12,"current":1,"output":true}`,
  todos opcionais; fora do limite → 422, erro do instrumento → 502) e
  `PATCH /api/equipment/{id}/poll` (`{"poll_ms":500}`).
- O proxy do Vite repassa o WebSocket (`ws: true` em `vite.config.js`).
