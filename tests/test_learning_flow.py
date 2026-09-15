import unittest
from unittest.mock import AsyncMock, patch

from controllers import learning_flow_controller


class RunPhaseTests(unittest.IsolatedAsyncioTestCase):

    async def test_planning_dispatches_to_start_planning(self):
        with patch.object(
            learning_flow_controller,
            "start_planning",
            new=AsyncMock(return_value=None)
        ) as start_planning:

            result = await learning_flow_controller.run_phase(
                bot="bot",
                ctx="ctx",
                phase="Planning",
                topic="algorithm",
                send_long_message="send_long_message"
            )

            start_planning.assert_awaited_once_with(
                bot="bot",
                ctx="ctx",
                topic="algorithm",
                send_long_message="send_long_message"
            )
            self.assertIsNone(result)

    async def test_monitoring_dispatches_to_start_monitoring(self):
        with patch.object(
            learning_flow_controller,
            "start_monitoring",
            new=AsyncMock(return_value=True)
        ) as start_monitoring:

            result = await learning_flow_controller.run_phase(
                bot="bot",
                ctx="ctx",
                phase="Monitoring",
                topic="algorithm",
                send_long_message="send_long_message"
            )

            start_monitoring.assert_awaited_once_with(
                bot="bot",
                ctx="ctx",
                topic="algorithm",
                send_long_message="send_long_message"
            )
            self.assertIsNone(result)

    async def test_monitoring_failure_returns_false(self):
        with patch.object(
            learning_flow_controller,
            "start_monitoring",
            new=AsyncMock(return_value=False)
        ):
            result = await learning_flow_controller.run_phase(
                bot="bot",
                ctx="ctx",
                phase="Monitoring",
                topic="algorithm"
            )

            self.assertFalse(result)

    async def test_evaluation_dispatches_with_goal_and_qp(self):
        algorithm_goals = {
            "LG01": {"qp": "QP01"}
        }

        with patch.object(
            learning_flow_controller,
            "start_evaluation",
            new=AsyncMock(return_value=True)
        ) as start_evaluation:

            result = await learning_flow_controller.run_phase(
                bot="bot",
                ctx="ctx",
                phase="Evaluation",
                topic="algorithm",
                goal_id="LG01",
                algorithm_goals=algorithm_goals,
                send_long_message="send_long_message"
            )

            start_evaluation.assert_awaited_once_with(
                bot="bot",
                ctx="ctx",
                topic="algorithm",
                goal_id="LG01",
                qp="QP01",
                send_long_message="send_long_message"
            )
            self.assertIsNone(result)

    async def test_evaluation_failure_returns_false(self):
        algorithm_goals = {
            "LG01": {"qp": "QP01"}
        }

        with patch.object(
            learning_flow_controller,
            "start_evaluation",
            new=AsyncMock(return_value=False)
        ):
            result = await learning_flow_controller.run_phase(
                bot="bot",
                ctx="ctx",
                phase="Evaluation",
                topic="algorithm",
                goal_id="LG01",
                algorithm_goals=algorithm_goals
            )

            self.assertFalse(result)

    async def test_unknown_phase_calls_nothing(self):
        with patch.object(
            learning_flow_controller,
            "start_planning",
            new=AsyncMock()
        ) as start_planning, patch.object(
            learning_flow_controller,
            "start_monitoring",
            new=AsyncMock()
        ) as start_monitoring, patch.object(
            learning_flow_controller,
            "start_evaluation",
            new=AsyncMock()
        ) as start_evaluation:

            result = await learning_flow_controller.run_phase(
                bot="bot",
                ctx="ctx",
                phase="Unknown",
                topic="algorithm"
            )

            start_planning.assert_not_awaited()
            start_monitoring.assert_not_awaited()
            start_evaluation.assert_not_awaited()
            self.assertIsNone(result)


class RunLearningFlowTests(unittest.IsolatedAsyncioTestCase):

    async def test_missing_goal_sends_error_and_skips_phases(self):
        ctx = AsyncMock()

        with patch.object(
            learning_flow_controller,
            "run_phase",
            new=AsyncMock()
        ) as run_phase:

            await learning_flow_controller.run_learning_flow(
                bot="bot",
                ctx=ctx,
                goal_id="MISSING",
                algorithm_goals={}
            )

            ctx.send.assert_awaited_once()
            run_phase.assert_not_awaited()

    async def test_runs_each_phase_in_order(self):
        ctx = AsyncMock()

        algorithm_goals = {
            "LG01": {
                "name": "Algorithm Basics",
                "qp": "QP01",
                "phases": ["Planning", "Monitoring", "Evaluation"]
            }
        }

        with patch.object(
            learning_flow_controller,
            "run_phase",
            new=AsyncMock(return_value=None)
        ) as run_phase:

            await learning_flow_controller.run_learning_flow(
                bot="bot",
                ctx=ctx,
                goal_id="LG01",
                algorithm_goals=algorithm_goals,
                topic="algorithm"
            )

            self.assertEqual(run_phase.await_count, 3)

            called_phases = [
                call.kwargs["phase"]
                for call in run_phase.await_args_list
            ]

            self.assertEqual(
                called_phases,
                ["Planning", "Monitoring", "Evaluation"]
            )

            for call in run_phase.await_args_list:
                self.assertEqual(call.kwargs["goal_id"], "LG01")
                self.assertIs(
                    call.kwargs["algorithm_goals"],
                    algorithm_goals
                )


if __name__ == "__main__":
    unittest.main()
