"""
Insurance Document Intelligence Assistant
Evaluation Module - API Routes

Flask blueprint providing evaluation endpoints.
These are independent from the main chat routes.
"""

from flask import Blueprint, request, jsonify

from ..security import get_audit_logger
from .evaluator import get_evaluator
from .robustness import get_robustness_tester

eval_api = Blueprint("eval_api", __name__)
logger = get_audit_logger()


@eval_api.route("/evaluate", methods=["POST"])
def evaluate_rag():
    """
    Run single-call RAGAS evaluation on a question.

    POST /api/eval/evaluate
    Body: {"question": "...", "ground_truth": "..." (optional)}

    Evaluation results are printed to the terminal/log.
    API returns JSON response for programmatic access.
    """
    data = request.get_json()

    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' in request body"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400

    ground_truth = data.get("ground_truth")

    try:
        evaluator = get_evaluator()
        result = evaluator.evaluate(
            question=question,
            ground_truth=ground_truth,
        )

        # Results are already printed to terminal by evaluator._log_and_print()
        return jsonify({
            "status": "success",
            "evaluation": result.to_dict(),
        })

    except Exception as e:
        logger.log(
            "evaluation_error",
            "evaluation",
            {"error": str(e)},
            status="error",
        )
        return jsonify({
            "status": "error",
            "error": f"Evaluation failed: {str(e)}",
        }), 500


@eval_api.route("/robustness", methods=["POST"])
def test_robustness():
    """
    Run Giskard-style robustness tests.

    POST /api/eval/robustness
    Body: {"question": "..."}

    Returns robustness scores and hallucination risk.
    """
    data = request.get_json()

    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' in request body"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400

    try:
        tester = get_robustness_tester()
        result = tester.test_robustness(question=question)

        return jsonify({
            "status": "success",
            "robustness": result.to_dict(),
        })

    except Exception as e:
        logger.log(
            "robustness_test_error",
            "evaluation",
            {"error": str(e)},
            status="error",
        )
        return jsonify({
            "status": "error",
            "error": f"Robustness test failed: {str(e)}",
        }), 500
