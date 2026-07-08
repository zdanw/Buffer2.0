import requests

url = "https://huggingface.co/api/spaces/zongsechenai/Bebcare_Buffer/logs/run"
headers = {"Authorization": "Bearer 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"}

# 使用 stream=True 来模拟 curl -N 接收持续输出的日志
response = requests.get(url, headers=headers, stream=True)

for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))