import json
import os

# โฟลเดอร์ Knowledge Base
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge_base")


def load_topic(topic: str):
    """
    โหลดไฟล์ JSON ตามชื่อหัวข้อ

    เช่น
        load_topic("algorithm")
        load_topic("flowchart")
        load_topic("pseudocode")
    """

    filename = f"{topic.lower()}.json"
    filepath = os.path.join(KNOWLEDGE_DIR, filename)

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"ไม่พบไฟล์ {filename}")

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_planning_questions(topic: str):
    data = load_topic(topic)
    return data.get("planning", [])


def get_monitoring_questions(topic: str):
    data = load_topic(topic)
    return data.get("monitoring", [])


def get_evaluation_questions(topic: str):
    data = load_topic(topic)
    return data.get("evaluation", [])


def get_learning_objectives(topic: str):
    data = load_topic(topic)
    return data.get("learning_objectives", [])


def get_common_mistakes(topic: str):
    data = load_topic(topic)
    return data.get("common_mistakes", [])


def get_description(topic: str):
    data = load_topic(topic)
    return data.get("description", "")