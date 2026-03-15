from typing import Dict, Any
from tasks.base_task import BaseTask

class TestTask(BaseTask):
    def __init__(self):
        # Initializing with dummy values for testing
        super().__init__(base_url="https://httpbin.org", task_name="test_task")

    def run(self) -> Dict[str, Any]:
        self.logger.info("Running TestTask...")
        
        # Simulating some logic
        data_to_verify = {
            "message": "Hello, this is a test task!",
            "status": "success"
        }
        
        self.logger.info(f"Data to verify: {data_to_verify}")
        
        # In a real scenario, we would call self.verify(data_to_verify)
        # For now, we just return the data as a success indicator
        return data_to_verify
