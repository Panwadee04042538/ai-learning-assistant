import json
from pathlib import Path


# ==========================================
# File Paths
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "knowledge_base" / "algorithm.json"
OUTPUT_FILE = BASE_DIR / "knowledge_base" / "algorithm_v3.json"


# ==========================================
# KU → LG Mapping
# ==========================================

KU_LG_MAPPING = {

    # --------------------------------------
    # 2.1 การวิเคราะห์ปัญหา
    # --------------------------------------

    "KU01": ["LG02"],
    "KU02": ["LG02"],
    "KU03": ["LG02"],
    "KU04": ["LG02"],
    "KU05": ["LG02"],
    "KU06": ["LG02"],


    # --------------------------------------
    # 2.2 อัลกอริทึมเบื้องต้น
    # --------------------------------------

    "KU07": ["LG01"],


    # --------------------------------------
    # 2.2.2 รูปแบบการแก้ปัญหาด้วย Algorithm
    # --------------------------------------

    "KU08": ["LG04", "LG06"],
    "KU09": ["LG04", "LG06"],
    "KU10": ["LG04", "LG06"],
    "KU11": ["LG04", "LG06"],

}


# ==========================================
# Load JSON
# ==========================================

print("📂 Loading algorithm.json...")

with open(INPUT_FILE, "r", encoding="utf-8") as file:
    data = json.load(file)


# ==========================================
# Find Knowledge Units
# ==========================================

knowledge_units = data.get("knowledge_units", [])

print(f"📚 Found {len(knowledge_units)} Knowledge Units")


# ==========================================
# Add related_lg
# ==========================================

updated_count = 0
missing_mapping = []

for unit in knowledge_units:

    ku_id = unit.get("ku_id")

    if ku_id in KU_LG_MAPPING:

        unit["related_lg"] = KU_LG_MAPPING[ku_id]

        updated_count += 1

        print(
            f"✅ {ku_id} → "
            f"{', '.join(KU_LG_MAPPING[ku_id])}"
        )

    else:

        missing_mapping.append(ku_id)

        print(f"⚠️ {ku_id} → No LG Mapping")


# ==========================================
# Save New JSON
# ==========================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        data,
        file,
        ensure_ascii=False,
        indent=2
    )


# ==========================================
# Summary
# ==========================================

print("\n==========================================")
print("🎉 Migration Complete")
print("==========================================")

print(f"Updated KU: {updated_count}")

if missing_mapping:

    print("\n⚠️ KU without mapping:")

    for ku_id in missing_mapping:
        print(f" - {ku_id}")

else:

    print("\n✅ All KU have LG Mapping")

print(f"\n📄 Output File:")
print(OUTPUT_FILE)