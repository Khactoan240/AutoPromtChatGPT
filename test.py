from fake_chatgpt_api import FakeChatGPTAPI

fake = FakeChatGPTAPI()
response = fake.send_request("testing a water with a gun")
print(response)