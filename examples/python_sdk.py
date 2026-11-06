"""After installing PromptBoundary, run: python examples/python_sdk.py"""
from promptboundary import BoundaryController, MockModel, StageModel, State

model = StageModel(MockModel(), generation={"temperature": 0})
controller = BoundaryController(model)
state = State()  # Own this per conversation. Only store it if the user expects memory.
for prompt in ("For this conversation, use bullet points.", "What is a comet?"):
    result = controller.run(state, prompt)
    state = result.state
    print(result.status, result.text)
