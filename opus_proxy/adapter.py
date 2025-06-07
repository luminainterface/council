import openai

def proxy_to_opus(raw_bytes: bytes) -> str:
    """
    Convert the upstream byte stream to UTF-8, replacing any invalid sequences.
    This prevents UnicodeDecodeError crashes and preserves creative output.
    """
    text = raw_bytes.decode("utf-8", errors="replace")
    
    # existing prompt re-write stays the same
    prompt = f"[OPUS] {text}"
    
    # Make OpenAI completion call
    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=150,
        temperature=0.7
    )
    
    openai_completion = response.choices[0].text.strip()
    return openai_completion 