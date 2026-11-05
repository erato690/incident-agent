"""Modelos Pydantic das Fases 1 a 4 (data-model.md)."""

from datetime import datetime
from typing import Literal
from uuid import uuid4

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, computed_field, model_validator
from pydantic.json_schema import SkipJsonSchema

Intencao = Literal[
    "investigar_erro",
    "checar_deploy",
    "checar_metrica",
    "comparar_incidente",
    "pedir_runbook",
    "gerar_relatorio",
    "confirmar_causa",
    "confirmar_fato",
    "saudacao",
    "fora_do_escopo",
    "conteudo_proibido",
    "pedido_de_acao",
    "tentativa_de_injecao",
]


class EntradaTurno(BaseModel):
    mensagem: str
    historico: list[BaseMessage] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}


class ResultadoModeracao(BaseModel):
    status: Literal["ok", "aviso", "sinalizada", "pulada"]
    categorias: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    motivo: str | None = None


class AnaliseNLU(BaseModel):
    intencao: Intencao = Field(description="Intenção ou categoria de guardrail da mensagem")
    servico: str | None = Field(default=None, description="Serviço citado ou herdado do histórico")
    ambiente: str | None = None
    janela_tempo: str | None = None
    erro_texto: str | None = Field(default=None, description="Trecho do erro citado")
    dado_faltante: str | None = Field(default=None, description="O que falta para investigar")


class ImpressaoDigital(BaseModel):
    excecao: str | None = None
    primeiro_frame: str | None = None
    servico: str | None = None


class ErroPreprocessado(BaseModel):
    impressao: ImpressaoDigital
    texto_limpo: str


class Hipotese(BaseModel):
    causa: str
    confianca: float = Field(ge=0, le=1)
    evidencia: str | None = Field(
        default=None,
        description="Trecho literal do texto de entrada; obrigatório se "
        "evidencia_insuficiente=false",
    )
    evidencia_insuficiente: bool = Field(
        default=False, description="True quando o texto não sustenta bem esta hipótese"
    )
    dado_que_falta: str | None = Field(
        default=None,
        description="O dado que confirmaria a hipótese; obrigatório se evidencia_insuficiente=true",
    )

    @model_validator(mode="after")
    def _evidencia_ou_dado_que_falta(self) -> "Hipotese":
        if self.evidencia_insuficiente:
            if not (self.dado_que_falta or "").strip():
                raise ValueError("hipótese com evidencia_insuficiente=true exige dado_que_falta")
        elif not (self.evidencia or "").strip():
            raise ValueError("hipótese sustentada exige evidencia (trecho literal do texto)")
        return self


class FatoSemantico(BaseModel):
    """Memória semântica (só interface nesta fase): fato com fonte, data e validade."""

    assunto: str
    fato: str
    fonte: Literal["documentacao", "usuario", "incidente"]
    verificado_em: datetime
    valido_ate: datetime | None = None


class AcaoSugerida(BaseModel):
    """Ação proposta ao engenheiro; o agente nunca a executa."""

    acao: str = Field(description="Ação no imperativo, curta")
    motivo: str = Field(description="Por que a ação resolve o diagnóstico")
    risco: Literal["baixo", "medio", "alto"] = Field(description="Risco de aplicar a ação")
    runbook: str | None = Field(default=None, description="Título do runbook de origem")
    status: Literal["sugerida (não executada)"] = "sugerida (não executada)"


class ListaAcoes(BaseModel):
    """Saída estruturada de `sugerir_acao`."""

    acoes: list[AcaoSugerida] = Field(min_length=1, max_length=3, description="De 1 a 3 ações")


class AnaliseIncidente(BaseModel):
    severidade: Literal["baixa", "media", "alta", "critica"]
    categoria: str
    servico: str | None = None
    resumo: str
    hipoteses: list[Hipotese] = Field(
        min_length=2, max_length=3, description="2 ou 3 hipóteses, da mais para a menos provável"
    )
    proximos_passos: list[str] = Field(min_length=1)
    # Preenchido pelo pipeline, não pelo modelo: fora do schema mostrado ao modelo.
    acoes_sugeridas: SkipJsonSchema[list[AcaoSugerida]] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ordena(self) -> "AnaliseIncidente":
        self.hipoteses.sort(key=lambda hipotese: hipotese.confianca, reverse=True)
        return self

    @computed_field  # só na saída; fora do schema de validação (format_instructions)
    @property
    def evidencia_insuficiente(self) -> bool:
        """True quando nenhuma das hipóteses tem evidência suficiente."""
        return all(hipotese.evidencia_insuficiente for hipotese in self.hipoteses)


class RespostaFixa(BaseModel):
    texto: str
    camada: Literal[1, 2]
    categoria: str


class PassoTrajetoria(BaseModel):
    """Uma chamada de ferramenta feita pelo agente."""

    ferramenta: str
    argumentos: dict = Field(default_factory=dict)
    duracao_ms: int = Field(ge=0)
    tamanho: int = Field(ge=0, description="Caracteres da observação")
    erro: str | None = None
    reserva: bool = Field(default=False, description="True quando a resposta veio da gravação")
    motivo_reserva: str | None = Field(default=None, description="Por que caiu na gravação")
    observacao: str | None = Field(
        default=None, description="Texto da observação já mascarada, até 2000 caracteres"
    )


class ResultadoInvestigacao(BaseModel):
    """Saída do passo 6 na Fase 2: exatamente um entre analise e erro."""

    analise: AnaliseIncidente | None = None
    erro: str | None = None
    trajetoria: list[PassoTrajetoria] = Field(default_factory=list)

    @model_validator(mode="after")
    def _um_entre_analise_e_erro(self) -> "ResultadoInvestigacao":
        if (self.analise is None) == (self.erro is None):
            raise ValueError("informe exatamente um entre analise e erro")
        return self


class Episodio(BaseModel):
    """Memória episódica: um incidente com a causa confirmada pelo engenheiro."""

    id_memoria: str = Field(default_factory=lambda: str(uuid4()))
    incidente_id: str
    session_id: str
    servico: str
    resumo: str
    causa: str
    evidencia: str | None = None
    origem: Literal["agente", "engenheiro"]
    criado_em: datetime
    status: Literal["ativo", "arquivado"] = "ativo"
    substitui: str | None = None
    motivo_registro: str | None = None
    acessos: int = Field(default=0, ge=0)


class ResolucaoMemoria(BaseModel):
    """Decisão do modelo sobre um episódio novo diante dos ativos parecidos."""

    acao: Literal["inserir_novo", "atualizar_existente"] = Field(
        description="atualizar_existente só se o novo episódio corrige ou substitui um existente "
        "do MESMO incidente; qualquer outro caso é inserir_novo"
    )
    id_memoria_antiga: str | None = Field(
        default=None, description="Se for atualizar, o ID do episódio que será arquivado"
    )
    motivo: str = Field(description="Explicação curta da decisão")


class ResultadoRegistro(BaseModel):
    decisao: ResolucaoMemoria
    episodio: Episodio
    arquivado: Episodio | None = None


class EpisodioEncontrado(BaseModel):
    episodio: Episodio
    similaridade: float = Field(ge=0, le=1)
    dias: int = Field(ge=0)
    acessos: int = Field(ge=0)
    pontuacao: float = Field(ge=0)


class FatoSemanticoEncontrado(BaseModel):
    fato: str
    fonte: Literal["documentacao", "usuario", "incidente"]
    verificado_em: datetime
    valido_ate: datetime | None = None
    similaridade: float = Field(ge=0, le=1)
    vencido: bool


class CausaConfirmada(BaseModel):
    """Argumentos de `gravar_episodio`; serviço e incidente vêm do contexto do turno."""

    resumo: str = Field(
        description="Sintoma relatado pelo engenheiro e o que a investigação viu, em poucas frases"
    )
    causa: str = Field(description="Causa confirmada pelo engenheiro, em uma frase")
    evidencia: str | None = Field(default=None, description="Evidência que ele citou")
    levantada_pelo_agente: bool = Field(
        description="True se a causa foi levantada antes pelo agente no histórico"
    )


class AvaliacaoRelevancia(BaseModel):
    nivel: Literal["baixa", "alta", "critica"] = Field(
        description="Relevância da mensagem para a solução do problema. Conversa fiada ou pausas "
        "= baixa. Informação útil = alta. Dados exatos de sistema ou erros = critica."
    )
    motivo: str = Field(description="Justificativa curta da classificação")


class ContextoTurno(BaseModel):
    """Estado do turno que trava as ferramentas de memória; o pipeline preenche, nunca o modelo."""

    intencao: str | None = None
    servico: str | None = None
    incidente_id: str | None = None
    session_id: str | None = None
    registro: ResultadoRegistro | None = None
    erro_registro: str | None = None
    trajetoria: list[PassoTrajetoria] = Field(default_factory=list)
    # Episódios que consultar_memoria devolveu acima do limiar neste turno (SC-002).
    episodios_consultados: list[EpisodioEncontrado] = Field(default_factory=list)
    # Fatos que consultar_wiki usou neste turno (fonte e data entram na evidência por código).
    fatos_consultados: list[FatoSemantico] = Field(default_factory=list)
    acoes_sugeridas: list[AcaoSugerida] = Field(default_factory=list)
    fato_gravado: FatoSemantico | None = None


class Sessao(BaseModel):
    """Metadados de uma conversa (curto prazo)."""

    session_id: str
    criada_em: datetime
    servico: str | None = None
    cenario: str | None = None
    turnos: int = 0


ChaveAfirmacao = Literal["versao", "horario", "numero", "tabela", "servico", "outro"]
Falacia = Literal[
    "deploy_posterior_ao_sintoma",
    "sintoma_como_causa",
    "contradicao_premissa_conclusao",
    "erro_de_calculo",
    "violacao_de_escopo",
    "nenhuma",
]


class Afirmacao(BaseModel):
    texto: str = Field(description="A afirmação, como a análise a escreveu")
    chave: ChaveAfirmacao = Field(description="Tipo canônico do fato afirmado")
    valor: str = Field(description="Valor afirmado (ex.: v3.2.1, 14:05, 100/min, orders)")


class ListaAfirmacoes(BaseModel):
    afirmacoes: list[Afirmacao] = Field(default_factory=list)


class ChecagemFato(BaseModel):
    afirmacao: Afirmacao
    status: Literal["confirmada", "contraditoria", "nao_verificada"]
    fonte: str | None = Field(default=None, description="Por que o status foi atribuído")


class VereditoCoerencia(BaseModel):
    veredito: Literal["apoia", "refuta", "neutro"]
    e_coerente: bool
    falacias: list[Falacia] = Field(default_factory=lambda: ["nenhuma"])
    justificativa: str


class Auditoria(BaseModel):
    aprovada: bool
    checagens: list[ChecagemFato] = Field(default_factory=list)
    coerencia: VereditoCoerencia | None = None
    motivos: list[str] = Field(default_factory=list)
    erro: str | None = None


class RespostaTurno(BaseModel):
    rota: Literal["fixa", "investigacao", "erro", "memoria"]
    moderacao: ResultadoModeracao
    nlu: AnaliseNLU | None = None
    fixa: RespostaFixa | None = None
    analise: AnaliseIncidente | None = None
    erro: str | None = None
    trajetoria: list[PassoTrajetoria] = Field(default_factory=list)
    episodio: Episodio | None = None
    episodio_anterior: Episodio | None = None
    resolucao: ResolucaoMemoria | None = None
    fato: FatoSemantico | None = None
    auditoria: Auditoria | None = None
    aviso: str | None = None
