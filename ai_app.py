from airllm import AutoModel

# Model nomini tekshirilgan manzilga o'zgartirdik
model_id = "unsloth/Meta-Llama-3.1-70B" 

# Agar hali ham xato bersa, tokenni to'g'ridan-to'g'ri shu yerga yozing:
# model = AutoModel.from_pretrained(model_id, token="hf_va_hokazo_sizning_tokeningiz")
model = AutoModel.from_pretrained(model_id)

input_text = ["Salom, qandaysan?"]
input_tokens = model.tokenizer(input_text, return_tensors="pt", return_attention_mask=False)
output = model.generate(input_tokens['input_ids'], max_new_tokens=20)

print(model.tokenizer.decode(output[0], skip_special_tokens=True))