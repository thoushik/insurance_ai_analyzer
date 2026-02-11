
try:
    from ragas.metrics import faithfulness
    print("Direct import: Success")
except ImportError:
    print("Direct import: Failed")

try:
    from ragas.metrics.faithfulness import faithfulness
    print("Module import: Success")
except ImportError:
    print("Module import: Failed")

try:
    from ragas.metrics import answer_relevance
    print("AnswerRelevance direct: Success")
except ImportError:
    print("AnswerRelevance direct: Failed")
    
try:
    import ragas.metrics
    print("Dir:", dir(ragas.metrics))
except ImportError:
    print("Import metrics package: Failed")
