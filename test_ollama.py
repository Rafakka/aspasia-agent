from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen3:4b",
    base_url="http://127.0.0.1:11434",
)

response = llm.invoke("Say only hello")

print(response.content)
