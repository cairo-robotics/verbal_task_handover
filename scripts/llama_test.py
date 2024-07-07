import transformers
import torch

model_id = "/media/kaleb/T7/Meta-Llama-3-8B-Instruct/"
huggingface_access_token = "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"

pipeline = transformers.pipeline("text-generation", model=model_id, batch_size=1,
                                 model_kwargs={"torch_dtype": torch.bfloat16},
                                 device_map="auto", max_new_tokens=1000)

while(True):
    prompt = input("Enter a prompt: ")
    print(pipeline(prompt))
