# Sistema de Relatórios de Pontos Notáveis - Sentinela BD

## Descrição
Sistema para geração de relatórios de pontos notáveis (POIs) a partir da API CREARE, com consolidação inteligente de eventos e classificação automática por grupos.

## Estrutura do Projeto

```
Sentinela_BD/
├── scripts/
│   └── pontos_notaveis/
│       └── gerar_relatorio_pontos_notaveis.py  # Script principal
├── data/
│   └── output/                                 # Relatórios gerados
├── backups/                                    # Backups de scripts e dados
├── Grupos.csv                                  # Arquivo de mapeamento POI -> Grupo
└── README.md                                   # Esta documentação
```

## Script Principal

### `scripts/pontos_notaveis/gerar_relatorio_pontos_notaveis.py`

**Funcionalidades:**
- Busca eventos das últimas 5 horas via API CREARE
- Filtra por IDs específicos (configurável)
- Consolida eventos consecutivos do mesmo veículo no mesmo POI
- Classifica POIs em grupos usando arquivo `Grupos.csv`
- Gera relatório CSV com análise detalhada

**Configuração de IDs:**
```python
IDS_PERMITIDOS = ['16619', '16622', '39450', '40452', '44459']
```

**Arquivo de saída:** `pontos_notaveis_final_[timestamp].csv`

## Classificação de Grupos

### Arquivo `Grupos.csv`
Define o mapeamento de POIs para grupos:
```csv
POI;GRUPO
Descarga Inocencia;Terminal
Terminal Inocencia;Não Mapeado
Terminal;Não Mapeado
```

### Grupos Disponíveis:
- **Terminal**: Operações de terminal e descarga principal
- **Descarga**: Operações de descarga secundárias
- **Carregamento**: Operações de carregamento
- **Fábrica**: Operações na fábrica
- **Parada Operacional**: Paradas operacionais diversas
- **Ponto Apoio**: Pontos de apoio
- **Manutenção**: Operações de manutenção
- **Não Mapeado**: POIs não classificados ou especiais

## Como Usar

### 1. Executar o Relatório:
```bash
cd /mnt/c/Users/eusebioagj/OneDrive/Sentinela_BD
python3 scripts/pontos_notaveis/gerar_relatorio_pontos_notaveis.py
```

### 2. Modificar Classificação de Grupos:
1. Editar arquivo `Grupos.csv`
2. Executar novamente o script

### 3. Alterar IDs Filtrados:
Editar no script a linha:
```python
IDS_PERMITIDOS = ['seus', 'ids', 'aqui']
```

## Estrutura do Relatório CSV

| Campo | Descrição |
|-------|-----------|
| Filial | Identificação da filial (RRP, TLS, etc) |
| Placa_Veiculo | Placa do veículo |
| Descricao_POI | Nome do ponto notável |
| Grupo_POI | Classificação do grupo |
| Data_Entrada | Data/hora de entrada no POI |
| Data_Saida | Data/hora de saída do POI |
| Status | Status do evento |
| Duracao | Duração em horas decimais |

## Últimas Alterações (07/08/2025)

### Classificações Atualizadas:
- **Descarga Inocencia**: Terminal (era "Não Mapeado")
- **Terminal Inocencia**: Não Mapeado (era "Terminal")
- **Terminal**: Não Mapeado (hardcoded)

### Limpeza Realizada:
- Removidos scripts obsoletos
- Consolidado em único script principal
- Organização de diretórios
- Backup de versões anteriores

## Credenciais API

O script usa credenciais OAuth2 hardcoded:
- Client ID: 56963
- Client Secret: (configurado no script)

## Suporte

Para suporte ou dúvidas sobre o sistema, verificar:
- Logs de execução no terminal
- Arquivos de backup em `backups/`
- Documentação técnica em `docs/`