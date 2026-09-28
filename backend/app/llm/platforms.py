"""The LLM serving platforms KFMS can use.

Everything except Ollama speaks the OpenAI chat-completions protocol, so one
client serves them all; a platform entry only records how it differs — its
default address, whether it needs a key, whether it leaves the network.
Adding another OpenAI-compatible platform is one entry here.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Platform:
    name: str
    label: str
    # "ollama" (native /api) or "openai" (/v1/chat/completions, /v1/models)
    protocol: str
    description: str
    default_base_url: str
    # "none", "optional" or "required"
    api_key: str
    hint: str
    # The address cannot be changed (a hosted API).
    fixed_base_url: bool = False
    # Questions and schema leave the organisation's network.
    external: bool = False
    # Cloud APIs answer quickly; local models can take minutes on a CPU.
    cloud: bool = False


PLATFORMS: List[Platform] = [
    Platform(
        name="ollama",
        label="Ollama",
        protocol="ollama",
        description="사내 서버의 로컬 LLM · 명령줄로 모델 설치",
        default_base_url="http://localhost:11434",
        api_key="none",
        hint="서버 주소를 넣으면 설치된 모델 목록을 불러옵니다.",
    ),
    Platform(
        name="lmstudio",
        label="LM Studio",
        protocol="openai",
        description="PC에서 화면으로 모델을 받아 실행",
        default_base_url="http://localhost:1234/v1",
        api_key="optional",
        hint=(
            "LM Studio의 Developer 탭에서 서버를 시작하세요. 다른 PC에서 접속하려면 "
            "'Serve on Local Network'를 켜고 그 PC의 IP로 주소를 바꾸세요."
        ),
    ),
    Platform(
        name="vllm",
        label="vLLM",
        protocol="openai",
        description="GPU 서버용 고성능 서빙 엔진",
        # vLLM defaults to 8000, which is the KFMS API's own port.
        default_base_url="http://localhost:8001/v1",
        api_key="optional",
        hint=(
            "vLLM 기본 포트 8000은 KFMS 서버와 겹치므로 --port 8001처럼 다른 포트로 "
            "실행하세요. --api-key로 실행했다면 같은 키를 입력하세요."
        ),
    ),
    Platform(
        name="openai_compatible",
        label="OpenAI 호환 (기타)",
        protocol="openai",
        description="llama.cpp · LocalAI · SGLang · TGI · OpenAI 등",
        default_base_url="",
        api_key="optional",
        hint="/v1로 끝나는 주소를 입력하세요. 예: http://서버:8080/v1",
    ),
    Platform(
        name="groq",
        label="Groq",
        protocol="openai",
        description="외부 클라우드 API · 빠른 응답",
        default_base_url="https://api.groq.com/openai/v1",
        api_key="required",
        hint="console.groq.com에서 발급한 API 키가 필요합니다.",
        fixed_base_url=True,
        external=True,
        cloud=True,
    ),
]

_BY_NAME = {p.name: p for p in PLATFORMS}


def get_platform(name: str) -> Optional[Platform]:
    return _BY_NAME.get(name)
