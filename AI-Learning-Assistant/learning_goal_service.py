import json
from pathlib import Path


class LearningGoalService:

    def __init__(self):

        # ==========================================
        # File Path
        # ==========================================

        base_dir = Path(__file__).resolve().parent

        self.data_file = (
            base_dir
            / "knowledge_base"
            / "algorithm_v3.json"
        )

        # ==========================================
        # Load JSON
        # ==========================================

        with open(
            self.data_file,
            "r",
            encoding="utf-8"
        ) as file:

            self.data = json.load(file)


        # ==========================================
        # Load Learning Goals
        # ==========================================

        self.learning_goals = {
            goal["lg_id"]: goal
            for goal in self.data.get(
                "learning_goal_mapping",
                []
            )
        }


    # ==========================================
    # Get Learning Goal from KU
    # ==========================================

    def get_learning_goals_from_ku(self, unit):

        if not unit:
            return []


        related_lg_ids = unit.get(
            "related_lg",
            []
        )


        results = []


        for lg_id in related_lg_ids:

            goal = self.learning_goals.get(lg_id)

            if goal:

                results.append(goal)


        return results


    # ==========================================
    # Get Primary Learning Goal
    # ==========================================

    def get_primary_learning_goal(self, unit):

        goals = self.get_learning_goals_from_ku(unit)

        if not goals:
            return None


        return goals[0]


    # ==========================================
    # Get Learning Goal by ID
    # ==========================================

    def get_learning_goal_by_id(self, lg_id):

        return self.learning_goals.get(lg_id)


# ==========================================
# Quick Test
# ==========================================

if __name__ == "__main__":

    service = LearningGoalService()

    print("\n🎯 Learning Goal Service Test\n")

    print(
        f"Loaded Learning Goals: "
        f"{len(service.learning_goals)}"
    )

    print("\nAvailable Learning Goals:")

    for lg_id, goal in service.learning_goals.items():

        print(
            f"{lg_id} → "
            f"{goal.get('learning_goal')}"
        )