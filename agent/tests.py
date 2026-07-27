from django.test import SimpleTestCase

from agent.tools import _scheduled_task_name


class ScheduledTaskNameTests(SimpleTestCase):
    def test_long_payload_does_not_overflow_periodic_task_name(self):
        name = _scheduled_task_name(
            "agent.tasks.send_email",
            ["customer@example.com", "Subject", "x" * 1000],
            {},
        )

        self.assertLessEqual(len(name), 200)
        self.assertNotIn("x" * 100, name)

# Create your tests here.
