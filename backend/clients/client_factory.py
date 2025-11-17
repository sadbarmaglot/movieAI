from openai import OpenAI, AsyncOpenAI

from clients.bq_client import BigQueryClient
from clients.kp_client import KinopoiskClient
from clients.openai_client import OpenAIClient
from clients.gc_client import GoogleCloudClient
from settings import KP_API_KEY

bq_client = BigQueryClient()
gc_client = GoogleCloudClient()
kp_client = KinopoiskClient(api_key=KP_API_KEY, gc_client=gc_client)
openai_client_base = OpenAI()
openai_client_base_async = AsyncOpenAI()
openai_client = OpenAIClient(openai_client_base=openai_client_base, kp_client=kp_client)

__all__ = [
    "bq_client",
    "kp_client",
    "openai_client_base",
    "openai_client",
    "openai_client_base_async"
]