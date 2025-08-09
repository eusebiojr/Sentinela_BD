# Sistema de Monitoramento de Veículos em POIs - Instruções do Projeto

## 📋 Visão Geral

Este projeto monitora a quantidade de veículos dentro de POIs (Points of Interest) de hora em hora, detectando desvios quando o número de veículos excede o SLA permitido e gerando eventos para tratativa.

## 🎯 Objetivo Principal

Transformar o script `gerar_rerlatorio_pontos_notaveis` existente para:
1. Adicionar informação de grupos aos POIs
2. Detectar desvios de SLA por grupo de POIs
3. Gerar base de dados de eventos de desvio
4. Enviar dados para tabela no GCP (projeto: sz-wsp-00009)
5. Integrar com sistema Sentinela WEB para justificativas dos analistas

## 📊 Estrutura de Dados

### Dados de Entrada (gerados pelo script atual)
```
Filial | Placa_Veiculo | Descricao_POI | Grupo_POI | Data_Entrada | Data_Saida | Status | Duracao
```
**Nota:** Quando `Data_Saida` está em branco, significa que o veículo ainda está no POI.

### Dados de Saída Esperados
```
Evento | Placa | Grupo | Data_entrada | Tempo_permanencia | Alerta
```

### Formato do Evento
```
{FILIAL}_{GRUPO}_{NIVEL_ALERTA}_{DATA}_{HORA}
```
Exemplo: `RRP_PontoApoioRRP_N1_09082025_120000`

## 🔄 Regras de Negócio

### SLA RRP
Fábrica: 8 veículos
Terminal: 15 veículos
Manutenção: 15 veículos
Ponto Apoio: 8 veículos

### SLA TLS
Fábrica: 8 veículos
Terminal: 15 veículos
Manutenção: 15 veículos
Ponto Apoio: 8 veículos

### 1. Níveis de Alerta (Escalação)
- **N1**: Primeira hora com desvio detectado
- **N2**: Segunda hora consecutiva com desvio
- **N3**: Terceira hora consecutiva com desvio
- **N4**: Quarta hora consecutiva com desvio
- **Reset**: Se não houver desvio em uma hora, a contagem é zerada

### 2. Horário de Verificação
- Verificações ocorrem de hora em hora
- Timestamps devem ser sempre em horas fechadas (ex: 12:00:00, não 12:20:00)
- Se o script rodar às 12:20, deve registrar como 12:00

### 3. Cálculo de Tempo de Permanência
- Tempo em horas desde a entrada até o momento da verificação
- Formato decimal (ex: 1.62 horas)

## 📁 Mapeamento de Grupos de POIs

### TAREFA 1: Implementar o seguinte mapeamento no código

| Filial | POI | Grupo |
|--------|-----|-------|
| TLS | Oficina Central JSL | Manutenção |
| TLS | Carregamento Fabrica | Fábrica |
| RRP | Descarga Inocencia | Terminal |
| RRP | Agua Clara | Agua Clara |
| RRP | Carregamento Fabrica RRP | Fábrica |
| TLS | FILA DESCARGA APT | Terminal |
| TLS | Descarga TAP | Terminal |
| TLS | PA Celulose | Ponto Apoio |
| RRP | Manutencao JSL RRP | Manutenção |
| RRP | Oficina JSL | Manutenção |
| RRP | Abastecimento Frotas RRP | Abastecimento |
| TLS | CEMAVI | Manutenção |
| TLS | POSTO DE ABASTECIMENTO | Abastecimento |
| TLS | JDIESEL | Manutenção |
| TLS | Fila abastecimento posto | Abastecimento |
| RRP | Manuten¿¿o Geral JSL RRP | Manutenção |
| TLS | SELVIRIA | Selviria |
| RRP | PA AGUA CLARA | Ponto Apoio |
| TLS | MONTANINI | Manutenção |
| TLS | AREA EXTERNA SUZANO | Area Externa |
| RRP | Posto Mutum | Posto Mutum |
| TLS | PB Lopes | Manutenção |
| RRP | Buffer Frotas | Buffer |
| TLS | PB LOPES SCANIA | Manutenção |
| TLS | MS3 LAVA JATO | Manutenção |
| TLS | ADEVAR | Manutenção |
| TLS | REBUCCI | Manutenção |
| TLS | FEISCAR | Manutenção |
| TLS | LM RADIADORES | Manutenção |
| TLS | ALBINO | Manutenção |
| TLS | DIESELTRONIC | Manutenção |
| TLS | Manutencao Celulose | Manutenção |

## 🚀 Tarefas de Implementação

### TAREFA 1: Adicionar Grupos aos POIs
- [ ] Criar dicionário/mapeamento com os grupos acima
- [ ] Aplicar mapeamento aos dados processados pelo script
- [ ] Validar que todos os POIs têm grupo associado

### TAREFA 2: Detectar Desvios de SLA
- [ ] Implementar contagem de veículos por grupo de POI
- [ ] Comparar com limites de SLA (definir limites por grupo)
- [ ] Identificar grupos em desvio a cada hora

### TAREFA 3: Gerar Eventos de Desvio
- [ ] Criar estrutura de evento com formato especificado
- [ ] Calcular tempo de permanência para cada veículo
- [ ] Gerenciar níveis de alerta (N1 a N4)
- [ ] Implementar lógica de reset quando não há desvio

### TAREFA 4: Preparar para Cloud Run
- [ ] Configurar script para execução agendada (hourly)
- [ ] Implementar logging adequado
- [ ] Adicionar tratamento de erros
- [ ] Criar Dockerfile se necessário

### TAREFA 5: Integração com GCP
- [ ] Configurar conexão com BigQuery
- [ ] Criar/atualizar schema da tabela de destino
- [ ] Implementar inserção dos eventos na tabela
- [ ] Projeto GCP: `sz-wsp-00009`

## 💡 Exemplo de Processamento

### Input (09/08/2025 às 12:00hrs)
```
9 veículos no POI "Agua Clara" (Grupo: Ponto Apoio RRP)
Todos sem Data_Saida (ainda no POI)
```

### Output Esperado
```
9 linhas de evento, todas com:
- Evento: RRP_PontoApoioRRP_N1_09082025_120000
- Alerta: Tratativa N1
- Tempo_permanencia: calculado individualmente
```

## 📝 Notas Importantes

1. **Verificação Horária**: O script deve rodar a cada hora e sempre registrar timestamps em horas fechadas
2. **Grupos são Agregadores**: Vários POIs podem pertencer ao mesmo grupo
3. **SLA por Grupo**: A verificação de desvio é feita por grupo, não por POI individual
4. **Persistência de Estado**: Necessário manter histórico de níveis (N1-N4) entre execuções

## 🔧 Configurações Necessárias

### Variáveis de Ambiente
```bash
GCP_PROJECT_ID=sz-wsp-00009
BIGQUERY_DATASET=sentinela
BIGQUERY_TABLE=eventos_desvio_poi
```

### Dependências Python Esperadas
```python
pandas
google-cloud-bigquery
datetime
pytz  # para timezone Brasil
```

## 📈 Métricas de Sucesso

1. Todos os POIs mapeados para grupos
2. Detecção precisa de desvios por hora
3. Geração correta de eventos com níveis escalados
4. Dados enviados com sucesso para BigQuery
5. Sistema Sentinela WEB consumindo os dados

## 🚨 Pontos de Atenção

- Caracteres especiais no nome dos POIs (ex: "Manuten¿¿o")
- Timezone: considerar horário de Brasília
- Performance: otimizar para grandes volumes de dados
- Idempotência: evitar duplicação de eventos se o script rodar múltiplas vezes

---

**Status do Projeto**: Em desenvolvimento
**Última Atualização**: 09/08/2025
**Responsável**: [Seu nome]
**Contato**: [Seu email]