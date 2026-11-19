print("DEBUG SCRIPT STARTED", flush=True)

from pathlib import Path
from research_agent import llm

prompt_path = Path("debug_synthesis_prompt.txt")

prompt = prompt_path.read_text(encoding="utf-8")

print("PROMPT LOADED", flush=True)

model = llm.get_llm()

response = model.invoke(prompt)

print("\n" + "=" * 80)
print("ISOLATED SYNTHESIS RESULT")
print("=" * 80)

print(response.text)
