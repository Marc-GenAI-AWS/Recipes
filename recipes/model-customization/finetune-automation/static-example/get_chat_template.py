from transformers import AutoTokenizer
import json
from aws_settings import HF_Key, LLAMA_MODEL_ID  # Your credentials and model ID

def get_chat_template(model_id: str) -> str:
    """Fetch the chat template string from a Hugging Face model's tokenizer."""
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id, token=HF_Key)
        return tokenizer.chat_template
    except Exception as e:
        return f"Error fetching chat template: {e}"

def main(model_id: str):
    template = get_chat_template(model_id)
    print(f"Chat template for model {model_id}:\n")
    print(template)
    # Save the template to a JSON file in the correct SageMaker format
    with open("template.json", "w", encoding="utf-8") as f:
        json.dump({"template": template}, f, ensure_ascii=False, indent=2)
    print("Template saved to template.json in SageMaker-compatible JSON format")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Get chat template from Hugging Face model tokenizer and save in SageMaker format.")
    parser.add_argument("--model_id", type=str, help="Hugging Face model ID")

    args = parser.parse_args()

    selected_model_id = args.model_id if args.model_id else LLAMA_MODEL_ID
    main(selected_model_id)
