# Benchmark

Create `questions.json` from the downloaded Python documentation before running
the pipeline. It must contain at least 20 manually verified questions: 15
`dev`, 5 `test`, and at least 3 questions with a real metadata `filter` (one in
the test split). Do not fill this file with invented answers or metrics.

Each question should contain `id`, `split`, `question`, `expected_answer`,
`gold_source_id`, `gold_page` (the HTML `unit_id`), and `evidence_quote`.
