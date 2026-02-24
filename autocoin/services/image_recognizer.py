"""
Image-based transaction recognition using multimodal LLMs.
Supports OpenAI (GPT-4o-mini) and Google Gemini (2.0 Flash).
"""

import asyncio
import base64
import json
import logging
import mimetypes
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import httpx

from autocoin.config import settings

logger = logging.getLogger(__name__)

# Structured prompt for extracting transactions from images
EXTRACTION_PROMPT = """你是一个专业的记账助手。请仔细分析这张图片，提取其中的所有交易/消费记录信息。

图片可能是：支付截图（微信/支付宝）、银行账单、信用卡账单、收据小票、或其他包含交易信息的图片。

请将每一条交易记录提取为以下 JSON 格式，返回一个 JSON 数组：

```json
[
  {
    "transaction_time": "YYYY-MM-DD HH:MM:SS",
    "direction": "expense 或 income 或 neutral",
    "amount": 数字(正数),
    "category": "分类，如餐饮、交通、购物、转账、工资等",
    "counterparty": "交易对方名称",
    "product": "商品或服务描述",
    "payment_method": "支付方式，如微信支付、支付宝、银行卡等",
    "remark": "备注信息"
  }
]
```

重要规则：
1. amount 必须是正数
2. direction: 花钱为 "expense"，收钱为 "income"，其他为 "neutral"
3. 信用卡账单特殊规则：信用卡账单中 +（正数）表示消费/支出（direction="expense"），-（负数）表示还款或退款（direction="income"）
4. transaction_time: 如果图片中没有完整时间，用今天的日期 + "00:00:00"
5. 如果图片中有多条交易记录，全部提取
6. 如果无法识别任何交易信息，返回空数组 []
7. 只返回 JSON 数组，不要返回其他内容

今天的日期是：{today}
"""


def _get_extraction_prompt() -> str:
    """Build the extraction prompt with today's date."""
    return EXTRACTION_PROMPT.replace("{today}", datetime.now().strftime("%Y-%m-%d"))


def _encode_image(image_bytes: bytes, content_type: str) -> str:
    """Encode image bytes to base64 data URI."""
    return base64.b64encode(image_bytes).decode("utf-8")


def _parse_llm_response(text: str) -> list[dict]:
    """Parse the LLM response text into a list of transaction dicts."""
    text = text.strip()
    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            result = json.loads(text[start : end + 1])
        else:
            logger.error("Failed to parse LLM response as JSON: %s", text[:200])
            return []

    if isinstance(result, dict):
        # Some models may wrap in {"transactions": [...]}
        for key in ("transactions", "data", "items", "records"):
            if key in result and isinstance(result[key], list):
                result = result[key]
                break
        else:
            result = [result]

    if not isinstance(result, list):
        return []

    # Validate and clean up each transaction
    cleaned = []
    for item in result:
        if not isinstance(item, dict):
            continue
        try:
            amount = float(item.get("amount", 0))
        except (ValueError, TypeError):
            amount = 0.0
        if amount <= 0:
            continue

        direction = item.get("direction", "expense")
        if direction not in ("income", "expense", "neutral"):
            direction = "expense"

        cleaned.append(
            {
                "transaction_time": item.get("transaction_time", ""),
                "direction": direction,
                "amount": amount,
                "category": item.get("category", ""),
                "counterparty": item.get("counterparty", ""),
                "product": item.get("product", ""),
                "payment_method": item.get("payment_method", ""),
                "remark": item.get("remark", ""),
            }
        )

    return cleaned


class ImageRecognizer(ABC):
    """Base class for image recognizers."""

    @abstractmethod
    async def recognize(
        self, images: list[tuple[bytes, str]]
    ) -> list[dict]:
        """
        Recognize transactions from one or more images.

        Args:
            images: list of (image_bytes, content_type) tuples

        Returns:
            list of transaction dicts
        """
        ...


def _get_proxy_url() -> Optional[str]:
    """Read proxy from shell environment variables."""
    return (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
    )


def _needs_proxy(provider_name: str) -> bool:
    """Return True if the provider likely needs a proxy (foreign APIs)."""
    return provider_name in ("openai", "gemini")


# Maximum images per single API call, by provider.
# When more images are uploaded, we split into batches.
_MAX_IMAGES_PER_REQUEST: dict = {
    "zhipu": 5,     # glm-4v-plus-0111 limit
    # Other providers: no hard split needed (OpenAI supports many)
}


class OpenAICompatibleRecognizer(ImageRecognizer):
    """
    Recognizer using OpenAI-compatible chat completions API.
    Works with OpenAI, Zhipu (智谱), Qwen (通义千问), Deepseek, etc.
    """

    def __init__(self, api_key: str, model: str, base_url: str = "", provider_name: str = "openai"):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url
        self._provider_name = provider_name

    async def recognize(
        self, images: list[tuple[bytes, str]]
    ) -> list[dict]:
        # Split into batches if the provider has per-request image limits
        batch_size = _MAX_IMAGES_PER_REQUEST.get(self._provider_name)
        if batch_size and len(images) > batch_size:
            all_txs: list[dict] = []
            for i in range(0, len(images), batch_size):
                batch = images[i : i + batch_size]
                logger.info(
                    "%s: processing batch %d/%d (%d images)",
                    self._provider_name,
                    i // batch_size + 1,
                    (len(images) + batch_size - 1) // batch_size,
                    len(batch),
                )
                txs = await self._recognize_single(batch)
                all_txs.extend(txs)
            return all_txs
        return await self._recognize_single(images)

    async def _recognize_single(
        self, images: list[tuple[bytes, str]]
    ) -> list[dict]:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError(
                "openai package is not installed. "
                "Run: uv add openai"
            )

        if not self._api_key:
            raise ValueError(
                f"API key for {self._provider_name} is not configured. "
                f"Set AUTOCOIN_{self._provider_name.upper()}_API_KEY"
            )

        timeout_sec = settings.llm_timeout
        client_kwargs: dict = {
            "api_key": self._api_key,
            "timeout": timeout_sec,
        }
        if self._base_url:
            client_kwargs["base_url"] = self._base_url

        # Proxy for foreign APIs (OpenAI etc.)
        if _needs_proxy(self._provider_name):
            proxy_url = _get_proxy_url()
            if proxy_url:
                logger.info("Using proxy %s for %s", proxy_url, self._provider_name)
                client_kwargs["http_client"] = httpx.AsyncClient(
                    proxy=proxy_url,
                    timeout=timeout_sec,
                )
        else:
            # For Chinese providers, explicitly disable proxy so the SDK
            # doesn't auto-detect SOCKS proxies from ALL_PROXY etc.
            client_kwargs["http_client"] = httpx.AsyncClient(
                timeout=timeout_sec,
                trust_env=False,
            )

        client = AsyncOpenAI(**client_kwargs)

        # Build multimodal message content
        content: list[dict] = [{"type": "text", "text": _get_extraction_prompt()}]

        for img_bytes, content_type in images:
            b64 = _encode_image(img_bytes, content_type)
            image_url_obj: dict = {}
            if self._provider_name == "zhipu":
                # Zhipu: raw base64 (no data-URI prefix), no "detail" key
                image_url_obj["url"] = b64
            else:
                image_url_obj["url"] = f"data:{content_type};base64,{b64}"
                image_url_obj["detail"] = "high"
            content.append(
                {
                    "type": "image_url",
                    "image_url": image_url_obj,
                }
            )

        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": content}],
                    max_tokens=4096,
                    temperature=0.1,
                ),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"图片识别超时（{timeout_sec}秒），请稍后重试或减少图片数量"
            )

        text = response.choices[0].message.content or ""
        return _parse_llm_response(text)


class GeminiRecognizer(ImageRecognizer):
    """Google Gemini based image recognizer."""

    async def recognize(
        self, images: list[tuple[bytes, str]]
    ) -> list[dict]:
        try:
            from google import genai
        except ImportError:
            raise RuntimeError(
                "google-genai package is not installed. "
                "Run: uv add google-genai"
            )

        if not settings.gemini_api_key:
            raise ValueError("AUTOCOIN_GEMINI_API_KEY is not configured")

        timeout_sec = settings.llm_timeout

        # Proxy for Gemini (foreign API)
        proxy_url = _get_proxy_url()
        client_kwargs: dict = {"api_key": settings.gemini_api_key}
        if proxy_url:
            logger.info("Using proxy %s for gemini", proxy_url)
            client_kwargs["http_options"] = genai.types.HttpOptions(
                proxy=proxy_url,
                timeout=timeout_sec * 1000,  # milliseconds
            )

        client = genai.Client(**client_kwargs)

        # Build parts for Gemini
        parts = [_get_extraction_prompt()]

        for img_bytes, content_type in images:
            parts.append(
                genai.types.Part.from_bytes(
                    data=img_bytes,
                    mime_type=content_type,
                )
            )

        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.gemini_model,
                    contents=parts,
                    config=genai.types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=4096,
                    ),
                ),
                timeout=timeout_sec,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(
                f"图片识别超时（{timeout_sec}秒），请稍后重试或减少图片数量"
            )

        text = response.text or ""
        return _parse_llm_response(text)


# Provider configs: (api_key_attr, model_attr, base_url_attr)
_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai": ("openai_api_key", "openai_model", "openai_base_url"),
    "zhipu": ("zhipu_api_key", "zhipu_model", "zhipu_base_url"),
    "qwen": ("qwen_api_key", "qwen_model", "qwen_base_url"),
    "deepseek": ("deepseek_api_key", "deepseek_model", "deepseek_base_url"),
}

_ALL_PROVIDERS = set(_OPENAI_COMPATIBLE_PROVIDERS.keys()) | {"gemini"}


def _build_recognizer(provider: str) -> Optional[ImageRecognizer]:
    """
    Build a recognizer for the given provider.
    Returns None if the provider's API key is not configured.
    """
    if provider == "gemini":
        if not settings.gemini_api_key:
            return None
        return GeminiRecognizer()

    if provider in _OPENAI_COMPATIBLE_PROVIDERS:
        key_attr, model_attr, url_attr = _OPENAI_COMPATIBLE_PROVIDERS[provider]
        api_key = getattr(settings, key_attr)
        if not api_key:
            return None
        return OpenAICompatibleRecognizer(
            api_key=api_key,
            model=getattr(settings, model_attr),
            base_url=getattr(settings, url_attr),
            provider_name=provider,
        )

    return None


def get_recognizers() -> list[tuple[str, ImageRecognizer]]:
    """
    Return a list of (provider_name, recognizer) for all providers that
    have an API key configured, ordered by llm_provider_order.
    """
    order = [
        p.strip().lower()
        for p in settings.llm_provider_order.split(",")
        if p.strip()
    ]
    # Append any configured providers not explicitly listed
    for p in _ALL_PROVIDERS:
        if p not in order:
            order.append(p)

    result: list[tuple[str, ImageRecognizer]] = []
    for provider in order:
        recognizer = _build_recognizer(provider)
        if recognizer is not None:
            result.append((provider, recognizer))

    return result


async def recognize_with_fallback(
    images: list[tuple[bytes, str]],
) -> list[dict]:
    """
    Try each configured provider in order until one succeeds.
    Returns the recognized transactions from the first successful provider.
    Raises ValueError if no providers are configured, or RuntimeError
    if all configured providers fail.
    """
    recognizers = get_recognizers()
    if not recognizers:
        raise ValueError(
            "未配置任何 LLM API Key。请至少设置一个: "
            + ", ".join(
                f"AUTOCOIN_{p.upper()}_API_KEY" for p in _ALL_PROVIDERS
            )
        )

    errors: list[tuple[str, str]] = []
    for provider_name, recognizer in recognizers:
        try:
            logger.info("Trying provider: %s", provider_name)
            result = await recognizer.recognize(images)
            logger.info("Provider %s succeeded, got %d transactions", provider_name, len(result))
            return result
        except Exception as e:
            err_msg = str(e)
            logger.warning("Provider %s failed: %s", provider_name, err_msg)
            errors.append((provider_name, err_msg))
            continue

    # All providers failed
    detail_lines = "; ".join(f"{name}: {msg}" for name, msg in errors)
    raise RuntimeError(f"所有识别服务均失败 — {detail_lines}")
