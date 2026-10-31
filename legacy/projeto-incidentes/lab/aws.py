"""Clientes boto3 do laboratório.

LAB_AWS_MODE=moto (padrão) aponta para o servidor moto local.
LAB_AWS_MODE=aws usa as credenciais normais da AWS (profile ou variáveis de ambiente).
"""

import os

import boto3

REGIAO = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MOTO_URL = os.getenv("LAB_MOTO_URL", "http://127.0.0.1:5000")


def modo() -> str:
    return os.getenv("LAB_AWS_MODE", "moto")


def cliente(servico: str):
    kwargs = {"region_name": REGIAO}
    if modo() == "moto":
        kwargs.update(
            endpoint_url=MOTO_URL,
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
    return boto3.client(servico, **kwargs)
