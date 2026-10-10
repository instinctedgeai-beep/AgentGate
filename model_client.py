import os
import time

from policy_engine import Decision

def execute(prompt: str, decision: Decision, mode="simulate") -> dict:
    """Route requests without sending private data to hosted NVIDIA."""

    if mode == "simulate":
        return {
            "status": "SIMULATED",
            "response": "[Simulation] Request would use " + decision.route + " route.",
            "inference_ms": None,
            "tokens": None,
            "cost_usd": None,
        }

    if mode != "live":
        raise ValueError("mode must be simulate or live")

    from openai import OpenAI

    if decision.route == "PRIVATE":
        base_url = os.getenv("PRIVATE_NIM_BASE_URL")

        if not base_url:
            return {
                "status": "BLOCKED",
                "response": "No private NIM endpoint configured. No data transmitted.",
                "inference_ms": None,
                "tokens": None,
                "cost_usd": None,
            }

        if not (
            base_url.startswith("http://localhost:")
            or base_url.startswith("http://127.0.0.1:")
        ):
            return {
                "status": "BLOCKED",
                "response": "MVP permits only localhost private endpoints.",
                "inference_ms": None,
                "tokens": None,
                "cost_usd": None,
            }

        client = OpenAI(
            base_url=base_url,
            api_key=os.getenv("PRIVATE_NIM_API_KEY", "EMPTY"),
            timeout=25,
        )
        model = os.getenv(
            "PRIVATE_NIM_MODEL", "nvidia/nemotron-3-super-120b-a12b"
        )

    else:
        if not os.getenv("NVIDIA_API_KEY"):
            return {
                "status": "BLOCKED",
                "response": "Missing NVIDIA_API_KEY. No data transmitted.",
                "inference_ms": None,
                "tokens": None,
                "cost_usd": None,
            }

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.environ["NVIDIA_API_KEY"],
            timeout=25,
        )
        model = os.getenv(
            "NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b"
        )

    started = time.perf_counter()

    try:
        result = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=160,
            temperature=0.2,
        )

        elapsed = round((time.perf_counter() - started) * 1000, 1)
        usage = result.usage

        return {
            "status": "COMPLETED",
            "response": result.choices[0].message.content or "",
            "inference_ms": elapsed,
            "tokens": getattr(usage, "total_tokens", None),
            "cost_usd": None,
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "response": f"{type(exc).__name__}: {str(exc)[:120]}",
            "inference_ms": round(
                (time.perf_counter() - started) * 1000, 1
            ),
            "tokens": None,
            "cost_usd": None,
        }
