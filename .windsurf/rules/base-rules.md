---
trigger: always_on
---

# Project overview
This project is dedicated to completing tasks from the AI Devs 4 training program.
For each lesson, a dedicated directory is created within the `tasks` folder following the format `SXXEXX` (e.g., `S01E01`, `S02E03`), where `S` represents the week and `E` represents the day of that week.
Within each daily directory (e.g., `S02E03`), task implementation classes are created, which must inherit from `BaseTask`. Typically, the main task class shares the same name as the directory, though additional implementations may be added for specific requirements.

Task implementation involves executing defined steps and submitting the final answer to the task hub API.
The hub is accessible via a web interface at: {HUB_BASE_URL}/.
Submitting an answer requires sending a POST request with a JSON body containing `apikey`, `task_name`, and `answer`.
The hub responds with either an error message or a flag in the format `{FLG:....}`, which is then manually entered on the hub's website.

# Technology stack
- Python 3.12+
- OpenAI Python SDK

## Coding guidelines

- Utilize type hints for better code clarity and type checking.
- Follow PEP 8 style guide for code formatting.
- Choose descriptive variable, function, and class names.
- Keep functions short and focused on a single responsibility.
- Document functions and classes with docstrings to explain their purpose.
- Handle errors and edge cases at the beginning of functions.
- Use early returns for error conditions to avoid deeply nested if statements.
- Place the happy path last in the function for improved readability.
- Avoid unnecessary else statements; use if-return pattern instead.
- Implement proper error logging and user-friendly error messages.
