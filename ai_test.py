"""Smoke test for the local Ollama provider. Run: python ai_test.py"""
from ai.llm import get_llm


if __name__ == "__main__":
    llm = get_llm()
    print(f"Provider: {llm.__class__.__name__}")
    print(f"Model: {getattr(llm, 'model', 'unknown')}")
    print(llm.generate("Reply with exactly: Ollama connection is working."))
