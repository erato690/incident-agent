"""Modelos Pydantic da Fase 1 (data-model.md)."""
from typing import Literal

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, field_validator, model_validator

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
    status: Literal["ok", "sinalizada", "pulada"]
    categorias: list[str] = Field(default_factory=list)
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
    evidencia: str = Field(description="Trecho literal do texto de entrada")

    @field_validator("evidencia")
    @classmethod
    def _evidencia_nao_vazia(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("evidencia não pode ser vazia")
        return v


class AnaliseIncidente(BaseModel):
    severidade: Literal["baixa", "media", "alta", "critica"]
    categoria: str
    servico: str | None = None
    resumo: str
    hipoteses: list[Hipotese]
    evidencia_insuficiente: bool = False
    proximos_passos: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _ordena_e_valida(self) -> "AnaliseIncidente":
        if not self.hipoteses and not self.evidencia_insuficiente:
            raise ValueError("sem hipóteses exige evidencia_insuficiente=True")
        self.hipoteses.sort(key=lambda h: h.confianca, reverse=True)
        return self


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
