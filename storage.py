import json

def load_json(file_path):
	try:
		with open(file_path, "r", encoding="utf-8") as file:
			return json.load(file)
	except FileNotFoundError:
		return []

	except json.JSONDecodeError:
		return []

def save_json(file_path, data):
	with open(file_path, "w", encoding="utf-8") as file:
		json.dump(data, file, indent=4, ensure_ascii=False)