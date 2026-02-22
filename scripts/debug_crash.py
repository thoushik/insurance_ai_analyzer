import sys
import traceback

sys.path.insert(0, ".")

try:
    from app.evaluation.evaluator import get_evaluator
    evaluator = get_evaluator()
    print("Evaluator loaded. Running eval...")
    
    result = evaluator.evaluate("What is the loss ratio?")
    print("SUCCESS")
    print(result.to_dict())
except Exception as e:
    print(f"CRASH: {e}")
    traceback.print_exc()
