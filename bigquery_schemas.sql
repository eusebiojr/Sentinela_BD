-- Esquemas das Tabelas BigQuery para Sistema de Detecção de Desvios
-- Projeto: sz-wsp-00009
-- Dataset: sentinela_bd

-- ============================================================================
-- 1. TABELA DE VEÍCULOS ATIVOS
-- ============================================================================
CREATE TABLE IF NOT EXISTS `sz-wsp-00009.sentinela_bd.veiculos_ativos` (
  -- Identificação temporal
  timestamp_verificacao TIMESTAMP NOT NULL,
  execution_id STRING NOT NULL,
  
  -- Dados do veículo
  placa_veiculo STRING NOT NULL,
  evento_id STRING,
  
  -- Localização
  poi STRING NOT NULL,
  filial STRING NOT NULL,
  grupo STRING NOT NULL,
  
  -- Tempos
  data_entrada TIMESTAMP NOT NULL,
  tempo_permanencia_horas FLOAT64 NOT NULL,
  
  -- Status SLA
  limite_sla INTEGER,
  qtd_grupo INTEGER NOT NULL,
  status_sla STRING NOT NULL, -- 'OK' ou 'DESVIO'
  em_desvio BOOLEAN NOT NULL,
  
  -- Metadados
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(timestamp_verificacao)
CLUSTER BY filial, grupo, status_sla
OPTIONS(
  description="Registro horário de veículos ativos nos POIs monitorados",
  partition_expiration_days=365
);

-- ============================================================================
-- 2. TABELA DE EVENTOS DE DESVIO  
-- ============================================================================
CREATE TABLE IF NOT EXISTS `sz-wsp-00009.sentinela_bd.eventos_desvio` (
  -- Identificação do evento
  evento_id STRING NOT NULL,
  execution_id STRING NOT NULL,
  timestamp_verificacao TIMESTAMP NOT NULL,
  
  -- Dados do desvio
  filial STRING NOT NULL,
  grupo STRING NOT NULL,
  placa_veiculo STRING NOT NULL,
  poi STRING NOT NULL,
  
  -- Detalhes do desvio
  qtd_veiculos_grupo INTEGER NOT NULL,
  limite_sla INTEGER NOT NULL,
  excesso INTEGER NOT NULL, -- qtd_veiculos - limite_sla
  
  -- Dados temporais do veículo
  data_entrada TIMESTAMP NOT NULL,
  tempo_permanencia_horas FLOAT64 NOT NULL,
  
  -- Nível de escalonamento
  nivel_alerta STRING NOT NULL, -- N1, N2, N3, N4
  status_evento STRING DEFAULT 'ATIVO', -- ATIVO, RESOLVIDO, ESCALADO
  
  -- Ações tomadas
  acao_realizada STRING,
  responsavel STRING,
  observacoes STRING,
  
  -- Metadados
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(timestamp_verificacao)  
CLUSTER BY filial, grupo, nivel_alerta, status_evento
OPTIONS(
  description="Eventos de desvio de SLA com níveis de escalonamento N1-N4",
  partition_expiration_days=365
);

-- ============================================================================
-- 3. TABELA DE CONTROLE DE ESCALONAMENTO N1-N4
-- ============================================================================
CREATE TABLE IF NOT EXISTS `sz-wsp-00009.sentinela_bd.escalacoes_niveis` (
  -- Chave única do desvio (filial_grupo_data)  
  desvio_key STRING NOT NULL,
  execution_id STRING NOT NULL,
  
  -- Identificação do desvio
  filial STRING NOT NULL,
  grupo STRING NOT NULL,
  timestamp_inicio_desvio TIMESTAMP NOT NULL,
  timestamp_ultima_verificacao TIMESTAMP NOT NULL,
  
  -- Controle de níveis
  nivel_atual STRING NOT NULL, -- N1, N2, N3, N4
  horas_em_desvio INTEGER NOT NULL,
  quantidade_verificacoes INTEGER DEFAULT 1,
  
  -- Histórico de escalonamentos
  historico_niveis ARRAY<STRUCT<
    nivel STRING,
    timestamp_nivel TIMESTAMP,
    acao_realizada STRING,
    responsavel STRING
  >>,
  
  -- Próxima ação
  proximo_nivel STRING, -- Próximo nível de escalonamento
  proximo_nivel_em TIMESTAMP, -- Quando escalonar
  
  -- Status do desvio
  status STRING DEFAULT 'ATIVO', -- ATIVO, RESOLVIDO, CANCELADO
  resolvido_em TIMESTAMP,
  resolvido_por STRING,
  
  -- Metadados
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(timestamp_inicio_desvio)
CLUSTER BY filial, grupo, nivel_atual, status
OPTIONS(
  description="Controle de escalonamento de desvios por níveis N1-N4 com persistência de estado",
  partition_expiration_days=365
);

-- ============================================================================
-- 4. TABELA DE MÉTRICAS CONSOLIDADAS
-- ============================================================================  
CREATE TABLE IF NOT EXISTS `sz-wsp-00009.sentinela_bd.metricas_sla` (
  -- Dimensões temporais
  timestamp_verificacao TIMESTAMP NOT NULL,
  data_verificacao DATE NOT NULL,
  hora_verificacao INTEGER NOT NULL, -- 0-23
  execution_id STRING NOT NULL,
  
  -- Dimensões organizacionais
  filial STRING NOT NULL,
  grupo STRING NOT NULL,
  
  -- Métricas SLA
  limite_sla INTEGER NOT NULL,
  qtd_veiculos_ativos INTEGER NOT NULL,
  percentual_ocupacao FLOAT64 NOT NULL, -- (qtd_veiculos / limite) * 100
  
  -- Status
  em_desvio BOOLEAN NOT NULL,
  nivel_desvio STRING, -- N1, N2, N3, N4 (se em desvio)
  horas_consecutivas_desvio INTEGER DEFAULT 0,
  
  -- Métricas de performance
  tempo_processamento_segundos FLOAT64,
  total_pois_monitorados INTEGER,
  total_eventos_api INTEGER,
  
  -- Metadados
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY data_verificacao
CLUSTER BY filial, grupo, em_desvio
OPTIONS(
  description="Métricas consolidadas de SLA por hora para dashboards e relatórios",
  partition_expiration_days=90  -- 3 meses de retenção para métricas
);

-- ============================================================================
-- 5. TABELA DE LOGS DO SISTEMA
-- ============================================================================
CREATE TABLE IF NOT EXISTS `sz-wsp-00009.sentinela_bd.system_logs` (
  -- Identificação
  timestamp TIMESTAMP NOT NULL,
  execution_id STRING NOT NULL,
  log_level STRING NOT NULL, -- INFO, WARN, ERROR
  
  -- Contexto
  component STRING NOT NULL, -- 'api_client', 'sla_analyzer', 'bigquery_writer', etc
  operation STRING NOT NULL,
  
  -- Mensagem
  message STRING NOT NULL,
  details JSON,
  
  -- Métricas de performance
  duration_ms INTEGER,
  memory_usage_mb FLOAT64,
  
  -- Erro (se aplicável)
  error_code STRING,
  error_message STRING,
  stack_trace STRING,
  
  -- Metadados
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(timestamp)
CLUSTER BY log_level, component
OPTIONS(
  description="Logs estruturados do sistema para troubleshooting e auditoria",
  partition_expiration_days=30  -- 30 dias de retenção para logs
);

-- ============================================================================
-- 6. VIEW CONSOLIDADA PARA DASHBOARDS
-- ============================================================================
CREATE OR REPLACE VIEW `sz-wsp-00009.sentinela_bd.dashboard_desvios` AS
WITH latest_verification AS (
  SELECT 
    MAX(timestamp_verificacao) as ultimo_processamento
  FROM `sz-wsp-00009.sentinela_bd.metricas_sla`
),
current_status AS (
  SELECT 
    m.*,
    CASE 
      WHEN m.em_desvio THEN 
        CONCAT('🚨 DESVIO ', m.nivel_desvio, ' (', m.horas_consecutivas_desvio, 'h)')
      ELSE '✅ OK'
    END as status_display,
    CASE 
      WHEN m.percentual_ocupacao >= 100 THEN '🔴 CRÍTICO'
      WHEN m.percentual_ocupacao >= 80 THEN '🟡 ATENÇÃO'  
      ELSE '🟢 NORMAL'
    END as status_color
  FROM `sz-wsp-00009.sentinela_bd.metricas_sla` m
  CROSS JOIN latest_verification lv
  WHERE m.timestamp_verificacao = lv.ultimo_processamento
)
SELECT * FROM current_status
ORDER BY filial, grupo;

-- ============================================================================
-- 7. ÍNDICES E OTIMIZAÇÕES
-- ============================================================================

-- Criar índices para consultas frequentes (BigQuery não usa índices tradicionais, 
-- mas podemos otimizar com clustering e partitioning já definidos)

-- View para análise de tendências
CREATE OR REPLACE VIEW `sz-wsp-00009.sentinela_bd.tendencias_sla` AS
SELECT 
  filial,
  grupo,
  data_verificacao,
  AVG(percentual_ocupacao) as media_ocupacao,
  MAX(percentual_ocupacao) as pico_ocupacao,
  COUNT(CASE WHEN em_desvio THEN 1 END) as horas_desvio,
  COUNT(*) as total_horas
FROM `sz-wsp-00009.sentinela_bd.metricas_sla`
WHERE data_verificacao >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY filial, grupo, data_verificacao
ORDER BY data_verificacao DESC, filial, grupo;

-- ============================================================================
-- 8. STORED PROCEDURES PARA MANUTENÇÃO
-- ============================================================================

-- Procedure para limpeza de dados antigos
CREATE OR REPLACE PROCEDURE `sz-wsp-00009.sentinela_bd.cleanup_old_data`()
BEGIN
  -- Limpar logs mais antigos que 30 dias
  DELETE FROM `sz-wsp-00009.sentinela_bd.system_logs` 
  WHERE timestamp < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY);
  
  -- Limpar métricas mais antigas que 90 dias  
  DELETE FROM `sz-wsp-00009.sentinela_bd.metricas_sla`
  WHERE data_verificacao < DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY);
  
  -- Arquivar eventos de desvio resolvidos mais antigos que 1 ano
  DELETE FROM `sz-wsp-00009.sentinela_bd.eventos_desvio`
  WHERE timestamp_verificacao < TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
    AND status_evento = 'RESOLVIDO';
END;

-- Procedure para consolidação de métricas diárias
CREATE OR REPLACE PROCEDURE `sz-wsp-00009.sentinela_bd.consolidate_daily_metrics`(target_date DATE)
BEGIN
  -- Criar/atualizar tabela de métricas diárias consolidadas
  CREATE OR REPLACE TABLE `sz-wsp-00009.sentinela_bd.daily_metrics` AS
  SELECT 
    target_date as data,
    filial,
    grupo,
    COUNT(*) as total_verificacoes,
    AVG(percentual_ocupacao) as media_ocupacao,
    MAX(percentual_ocupacao) as pico_ocupacao,
    SUM(CASE WHEN em_desvio THEN 1 ELSE 0 END) as horas_desvio,
    MAX(horas_consecutivas_desvio) as max_horas_consecutivas
  FROM `sz-wsp-00009.sentinela_bd.metricas_sla`
  WHERE data_verificacao = target_date
  GROUP BY filial, grupo;
END;