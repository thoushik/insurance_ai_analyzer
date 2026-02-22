import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

prompt = """
You are a strict evaluation JSON API. Find how relevant the Answer is to the Question.
Output ONLY valid JSON matching this exact schema: {"score": float}
The score must be between 0.0 and 1.0. 1.0 = Direct, concise, perfect answer. 0.0 = Evasive, completely unrelated.

Question: What is the loss ratio?
Answer: The loss ratio is calculated as incurred losses divided by earned premiums.
"""

try:
    llm = ChatGroq(api_key=api_key, model_name="llama-3.1-8b-instant", temperature=0.0)
    result = llm.invoke(prompt)
    print("----- RAW LLM OUTPUT -----")
    print(repr(result.content))
    print("--------------------------")
    
    clean_json = result.content.strip().strip("`").removeprefix("json").strip()
    print(f"Cleaned string: {repr(clean_json)}")
    
    parsed = json.loads(clean_json)
    score = float(parsed.get("score", 0.5))
    print(f"SUCCESS. Score extracted: {score}")
    
except Exception as e:
    print(f"Crash: {e}")
