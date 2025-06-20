from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

def model_fn(model_dir):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    ).to(device)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    return {"model": model, "tokenizer": tokenizer, "device": device}

def predict_fn(data, model_dict):
    # Expecting data in the form: {"dialog": [{"role": ..., "content": ...}, ...]}
    dialog = data.get("dialog")
    if not dialog:
        raise ValueError("Input must contain a 'dialog' key with a list of messages.")

    # Build prompt from dialog
    prompt = ""
    for turn in dialog:
        role = turn["role"].capitalize()
        content = turn["content"]
        prompt += f"{role}: {content}\n"
    prompt += "Assistant:"  # Signal the model to generate the assistant's response

    tokenizer = model_dict["tokenizer"]
    model = model_dict["model"]
    device = model_dict["device"]

    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=256,
        early_stopping=True,
        repetition_penalty=1.2,
        eos_token_id=tokenizer.eos_token_id if tokenizer.eos_token_id is not None else None,
        pad_token_id=tokenizer.eos_token_id if tokenizer.eos_token_id is not None else None,
    )

    generated = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Extract only the assistant's answer (after the last "Assistant:" in the prompt)
    if "Assistant:" in generated:
        answer = generated.split("Assistant:")[-1].strip()
    else:
        answer = generated.strip()
    return {"generated_text": answer}
