"""Modelos Pydantic da Fase 1 (data-model.md)."""
from typing import Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

Intencao = Literal[
    "investigar_erro", "checar_deploy", "checar_metrica", "comparar_incidente",
    "pedir_runbook", "gerar_relatorio", "confirmar_causa", "saudacao",
    "fora_do_escopo", "conteudo_proibido", "pedido_de_acao", "tentativa_de_injecao",
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
        description="Trecho literal do texto de entrada; obrigatório se evidencia_insuficiente=false")
    evidencia_insuficiente: bool = Field(
        default=False, description="True quando o texto não sustenta bem esta hipótese")
    dado_que_falta: str | None = Field(
        default=None,
        description="O dado que confirmaria a hipótese; obrigatório se evidencia_insuficiente=true")

    @model_validator(mode="after")
    def _evidencia_ou_dado_que_falta(self) -> "Hipotese":
        if self.evidencia_insuficiente:
            if not (self.dado_que_falta or "").strip():
                raise ValueError("hipótese com evidencia_insuficiente=true exige dado_que_falta")
        elif not (self.evidencia or "").strip():
            raise ValueError("hipótese sustentada exige evidencia (trecho literal do texto)")
        return self


class AnaliseIncidente(BaseModel):
    severidade: Literal["baixa", "media", "alta", "critica"]
    categoria: str
    servico: str | None = None
    resumo: str
    hipoteses: list[Hipotese] = Field(
        min_length=2, max_length=3,
        description="2 ou 3 hipóteses, da mais para a menos provável")
    proximos_passos: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _ordena(self) -> "AnaliseIncidente":
        self.hipoteses.sort(key=lambda h: h.confianca, reverse=True)
        return self

    @computed_field  # só na saída; fora do schema de validação (format_instructions)
    @property
    def evidencia_insuficiente(self) -> bool:
        """True quando nenhuma das hipóteses tem evidência suficiente."""
        return all(h.evidencia_insuficiente for h in self.hipoteses)


class RespostaFixa(BaseModel):
    texto: str
    camada: Literal[1, 2]
    categoria: str


class RespostaTurno(BaseModel):
    rota: Literal["fixa", "investigacao", "erro"]
    moderacao: ResultadoModeracao
    nlu: AnaliseNLU | None = None
    fixa: RespostaFixa | None = None
    analise: AnaliseIncidente | None = None
    erro: str | None = None
