from research_agent.llm import get_llm

llm = get_llm()

response = llm.invoke("Say only hello")

print(response.content)