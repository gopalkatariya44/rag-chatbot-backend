from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_openai import OpenAIEmbeddings, ChatOpenAI


class ModelFactory:
    @staticmethod
    def get_embedding_model(model_name: str, provider: str, api_key: str):
        if provider == "openai":
            return OpenAIEmbeddings(model=model_name, openai_api_key=api_key)
        elif provider == "google":
            return GoogleGenerativeAIEmbeddings(model=f"models/{model_name}", google_api_key=api_key)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def get_chat_model(provider: str, api_key: str, model_name: str):
        if provider == "openai":
            return ChatOpenAI(openai_api_key=api_key, model_name=model_name)
        elif provider == "google":
            return ChatGoogleGenerativeAI(google_api_key=api_key, model=model_name)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
