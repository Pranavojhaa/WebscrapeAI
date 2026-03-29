import os
from dotenv import load_dotenv
from langchain_community.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

load_dotenv()

def dataframe_to_markdown(df):
    return df.to_markdown(index=False)

def summarize_paragraphs(paragraphs, max_length=1000):
    combined = "\n\n".join(paragraphs)
    if len(combined) > max_length:
        return combined[:max_length] + "\n\n... [truncated]"
    return combined

def start_chat_with_data(data):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the .env file!")

    llm = ChatOpenAI(api_key=api_key, model="gpt-3.5-turbo")
    memory = ConversationBufferMemory()

    preload_prompt = f"""
You are an AI assistant. The user has provided the following website data for analysis:
---------------------
{data}
---------------------
Please help them analyze it.
"""
    memory.chat_memory.add_user_message(preload_prompt)
    memory.chat_memory.add_ai_message("Got it! I'm ready to help analyze this data.")

    conversation = ConversationChain(llm=llm, memory=memory)

    print("\n💬 Start chatting about the scraped data! Type 'exit' to end.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("👋 Ending chat. Goodbye!")
            break
        response = conversation.run(user_input)
        print(f"AI: {response}\n")
