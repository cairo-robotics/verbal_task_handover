from openai import OpenAI
import yaml
import json

def load_config_data(filename="config.yaml"):
    with open(filename, "r") as f:
        args = yaml.safe_load(f)
        return args["OPENAI_API_KEY"], args["OPENAI_MODEL_VERSION"]
    
class GPTHandoverInterface:
    def __init__(self, api_key, model):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = 0.5

    def _gpt_response(self, system_role_message, prompt):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_role_message},
                {"role": "user", "content": prompt}
            ]
            temperature=self.temperature
        )
        return response
    
    def process_game_history(self, game_summary):
        raise NotImplementedError
    
    def process_handover_report(self, report):
        raise NotImplementedError

def main():
    api_key, model = load_config_data()
    client = OpenAI(api_key=api_key, model=model)

if __name__ == "__main__":
    main()    