# Sistema Sentinela BD - Monitor de Pontos Notáveis

## 📋 Descrição
Sistema para monitoramento e análise de pontos notáveis (POIs) de veículos utilizando a API da Creare Cloud. O sistema coleta eventos de entrada/saída em locais específicos nas últimas 5 horas e gera relatórios em formato CSV.

## 🎯 Objetivo
Monitorar veículos em locais específicos (POIs) das filiais RRP e TLS, consolidando eventos consecutivos e gerando relatórios detalhados para análise operacional.

## 🚀 Funcionalidades Principais

### 1. Coleta de Dados
- Busca eventos das **últimas 5 horas** via API Creare Cloud
- Filtragem automática por POIs específicos (RRP e TLS)
- Correção de timezone para Campo Grande/MS (UTC-4)
- Autenticação OAuth2 automatizada

### 2. Processamento de Dados
- **Consolidação inteligente**: Remove eventos consecutivos duplicados do mesmo POI
- **Classificação por filial**: Automática baseada nos POIs monitorados
- **Mapeamento de grupos**: Utiliza arquivo `Grupos.csv` para classificação
- **Cálculo de duração**: Permanência em cada local

### 3. Geração de Relatórios
- Arquivo CSV com timestamp automático
- Relatório detalhado no console com estatísticas
- Ordenação por veículo e cronologia

## 📁 Estrutura do Projeto

```
Sentinela_BD/
├── scripts/
│   └── pontos_notaveis/
│       └── gerar_relatorio_pontos_notaveis.py    # Script principal
├── sistema_antigo/                                # Códigos de referência
│   ├── C09_RRP.py
│   ├── C09_TLS.py
│   ├── C09_unificado.py
│   └── LÓGICA DOS DESVIOS HORA EM HORA.pdf
├── backup_projeto_20250809/                       # Backup de arquivos anteriores
├── Grupos.csv                                     # Mapeamento POI → Grupo
└── .env                                          # Credenciais (não versionado)
```

## 🏭 POIs Monitorados

### RRP (Ribas do Rio Pardo) - 11 locais
- Manutencao JSL RRP
- Carregamento Fabrica RRP
- Buffer Frotas
- Abastecimento Frotas RRP
- Oficina JSL
- Posto Mutum
- Agua Clara
- PA AGUA CLARA
- Descarga Inocencia
- Manuten¿¿o Geral JSL RRP (caracteres especiais)

### TLS (Três Lagoas) - 17 locais
- Carregamento Fabrica
- AREA EXTERNA SUZANO
- POSTO DE ABASTECIMENTO
- Fila abastecimento posto
- PA Celulose
- Manutencao Celulose
- MONTANINI, SELVIRIA, FILA DESCARGA APT
- Descarga TAP, PB Lopes
- Oficina Central JSL
- PB LOPES SCANIA, MS3 LAVA JATO
- REBUCCI, CEMAVI, FEISCAR
- DIESELTRONIC, LM RADIADORES
- ALBINO, JDIESEL, TRUCK LAZER

## 📊 Formato de Saída (CSV)

| Campo | Descrição |
|-------|-----------|
| Filial | RRP ou TLS |
| Placa_Veiculo | Placa do veículo |
| Descricao_POI | Nome do local |
| Grupo_POI | Grupo mapeado no Grupos.csv |
| Data_Entrada | Data/hora entrada (formato brasileiro) |
| Data_Saida | Data/hora saída (formato brasileiro) |
| Status | "Saiu da cerca" ou "Entrou na cerca" |
| Duracao | Tempo de permanência (decimal em horas) |

## ⚙️ Configuração

### Pré-requisitos
- Python 3.6+
- Bibliotecas padrão: `json`, `base64`, `urllib`, `csv`, `datetime`, `collections`, `os`

### Arquivos Necessários
1. **Grupos.csv**: Mapeamento de POIs para grupos
   - Formato: `POI;GRUPO` (separado por ponto-e-vírgula)
   - Encoding: UTF-8 com BOM

2. **.env**: Credenciais da API (não incluído no repositório)

## 🔧 Como Usar

### Execução Principal
```bash
cd scripts/pontos_notaveis/
python3 gerar_relatorio_pontos_notaveis.py
```

### Saída Esperada
- **Console**: Relatório detalhado com estatísticas
- **Arquivo**: `pontos_notaveis_FILTRO_POIS_YYYYMMDD_HHMMSS.csv`

## 🎯 Principais Recursos

### 1. Filtragem Inteligente
- Apenas POIs específicos são processados
- Suporte a caracteres especiais em nomes de POIs
- Classificação automática por filial

### 2. Consolidação de Eventos
- Remove registros duplicados consecutivos
- Mantém primeira entrada e última saída
- Otimiza a análise de permanência real

### 3. Timezone Correto
- Conversão automática UTC → Campo Grande (UTC-4)
- Datas apresentadas em formato brasileiro
- Cálculos precisos de duração

### 4. Relatório Detalhado
- Estatísticas por filial, veículo e POI
- Top 10 locais mais visitados
- Resumo geral do processamento

## 📈 Exemplo de Uso

```bash
$ python3 gerar_relatorio_pontos_notaveis.py

🚛 PONTOS NOTÁVEIS - FILTRO POR POIs - ÚLTIMAS 5 HORAS
🕐 Horário atual: 09/08/2025 09:15:30 (Campo Grande/MS)
📊 Total de POIs monitorados: 28

✅ Carregados 15 mapeamentos de grupos do arquivo Grupos.csv
📊 Total de eventos encontrados: 1,245
✅ Total de eventos após filtro de POIs: 156
✅ Eventos processados após filtro POI: 156
✅ Consolidação simplificada concluída: 134 eventos
📊 CSV gerado: pontos_notaveis_FILTRO_POIS_20250809_091530.csv

📈 RELATÓRIO DETALHADO
🏢 EVENTOS POR FILIAL:
   • TLS: 89 eventos
   • RRP: 45 eventos
```

## 🔍 Troubleshooting

### Problemas Comuns
1. **Erro de token**: Verificar credenciais no .env
2. **POI não encontrado**: Verificar se está na lista POIS_FILTRADOS
3. **Charset do CSV**: Arquivo usa UTF-8 com BOM para Excel

### Logs Importantes
- `✅ Carregados X mapeamentos`: Grupos.csv carregado com sucesso
- `📊 Total de eventos encontrados`: Eventos brutos da API
- `✅ Total após filtro`: Eventos dos POIs específicos
- `✅ Consolidação concluída`: Eventos após limpeza

## 🚀 Próximos Passos
1. Implementação de alertas automáticos
2. Dashboard web para visualização
3. Integração com banco de dados
4. Análise de desvios e anomalias

---

**Versão**: 2.0 - Reconstrução completa
**Última atualização**: 09/08/2025