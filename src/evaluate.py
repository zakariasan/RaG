def evaluate(
    student_search_results_path: str = 'data/output/search_results/UnansweredQuestions/dataset_code_public.json',
    dataset_path: str = 'data/datasets_public/public/UnansweredQuestions/dataset_code_public.json',
    k:int = 10,
    max_context_length: int = 2000
):
    """Check your answer protocol"""
    try:
        with open(student_search_results_path, encoding='utf-8') as f:
            questions = f.read()
        with open(dataset_path, encoding='utf-8') as f:
            ground_checker = f.read()

        print(questions)
        questions = questions.search_results
    except (OSError, PermissionError, FileNotFoundError) as e:
        print(e)
#    for question in student_search_results_path:

    print("Evaluation Results \n ========================================")


