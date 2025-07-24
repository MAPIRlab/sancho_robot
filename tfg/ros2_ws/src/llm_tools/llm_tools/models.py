from enum import Enum


class SmartStrEnum(str, Enum):
    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

class PROVIDER(SmartStrEnum):
    OPENAI = "openai"
    LLAMA = "llama"
    MISTRAL = "mistral"
    PHI = "phi"
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"
    SBERT = "sbert"
    E5 = "e5"
    BAAI = "baai"
    GEMMA = "gemma"
    FALCON = "falcon"
    YI = "yi"

class MODELS:
    class LLM:
        class OPENAI(SmartStrEnum):
            GPT_3_5_TURBO = "gpt-3.5-turbo"
            GPT_4 = "gpt-4"
            GPT_4O = "gpt-4o"

        class LLAMA(SmartStrEnum):
            LLAMA_3_1_8B_INSTRUCT = "meta-llama/Llama-3.1-8B-Instruct"
            LLAMA_3_3_70B_INSTRUCT = "meta-llama/Llama-3.3-70B-Instruct"

        class MISTRAL(SmartStrEnum):
            MISTRAL_7B = "mistralai/Mistral-7B-Instruct-v0.1"

        class PHI(SmartStrEnum):
            PHI_2 = "microsoft/phi-2"

        class QWEN(SmartStrEnum):
            QWEN_1_5_7B_CHAT = "Qwen/Qwen1.5-7B-Chat"
            QWEN_2_5_7B_IT = "Qwen/Qwen2.5-7B-Instruct"
            QWEN_2_5_14B_IT = "Qwen/Qwen2.5-14B-Instruct"
            QWEN_2_5_32B_IT = "Qwen/Qwen2.5-32B-Instruct"
            QWEN_2_5_72B_IT = "Qwen/Qwen2.5-72B-Instruct"

        class DEEPSEEK(SmartStrEnum):
            DEEPSEEK_LLM_7B_CHAT = "deepseek-ai/deepseek-llm-7b-chat"
            DEEPSEEK_LLM_67B_CHAT = "deepseek-ai/deepseek-llm-67b-chat"

            DEEPSEEK_R1_DISTILL_LLAMA_70B = "deepseek-ai/DeepSeek-R1-Distill-Llama-70B"
            DEEPSEEK_R1_DISTILL_QWEN_32B = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"

        class GEMINI(SmartStrEnum):
            GEMINI_1_5_FLASH = "gemini-1.5-flash-latest"
            GEMINI_2_0_FLASH_LITE = "gemini-2.0-flash-lite"
            GEMINI_2_5_FLASH = "gemini-2.5-flash"

        class GEMMA(SmartStrEnum):
            GEMMA_3_27B_IT = "google/gemma-3-27b-it"
        
        class FALCON(SmartStrEnum):
            FALCON_3_10B_IT = "tiiuae/Falcon3-10B-Instruct"
        
        class YI(SmartStrEnum):
            YI_1_5_9B_CHAT = "01-ai/Yi-1.5-9B-Chat"
            YI_1_5_34B_CHAT = "01-ai/Yi-1.5-34B-Chat"

    class EMBEDDING:
        class OPENAI(SmartStrEnum):
            SMALL_3 = "text-embedding-3-small"
            ADA_002 = "text-embedding-ada-002"
            LARGE_3 = "text-embedding-3-large"

        class QWEN(SmartStrEnum):
            QWEN_EMBED = "Alibaba-NLP/gte-Qwen2-7B-instruct"

        class DEEPSEEK(SmartStrEnum):
            DEEP_EMBED = "deepseek-ai/deepseek-coder-6.7b-instruct"

        class SBERT(SmartStrEnum):
            MINI_LM_L6_V2 = "sentence-transformers/all-MiniLM-L6-v2"

        class E5(SmartStrEnum):
            E5_LARGE_V2 = "intfloat/e5-large-v2"

        class BAAI(SmartStrEnum):
            BGE_M3 = "BAAI/bge-m3"
            BGE_BASE_EN = "BAAI/bge-base-en-v1.5"

NEEDS_API_KEY = {
    PROVIDER.GEMINI,
    PROVIDER.LLAMA,
    PROVIDER.MISTRAL,
    PROVIDER.OPENAI,
    PROVIDER.GEMMA
}

EXECUTED_LOCALLY = {
    PROVIDER.MISTRAL,
    PROVIDER.PHI,
    PROVIDER.QWEN,
    PROVIDER.DEEPSEEK,
    PROVIDER.SBERT,
    PROVIDER.E5,
    PROVIDER.BAAI
}