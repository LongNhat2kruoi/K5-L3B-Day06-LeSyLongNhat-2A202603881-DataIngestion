# Ý nghĩa repo và quy trình chạy

## Repo này dùng để làm gì?

Repo xây dựng một pipeline RAG cho Python Documentation. Mục tiêu là biến 30
unit HTML của Python 3.15.2 thành các chunk có thể truy xuất, so sánh ba chiến
lược chuẩn bị dữ liệu và đo chất lượng evidence.

Kết quả benchmark cho thấy:

| Strategy | Hit@1 | Evidence Hit@3 |
|---|---:|---:|
| A — fixed-size | 6/20 | 8/20 |
| B — paragraph | 7/20 | 14/20 |
| C — paragraph + filter | 9/20 | 17/20 |

Strategy C được chọn vì có Evidence Hit@3 cao nhất. Web demo bổ sung lớp answer
generation bằng OpenRouter, nhưng lớp này không thay thế benchmark retrieval.

## Quy trình

```text
Python Documentation HTML
        ↓
ingestion + normalize + metadata
        ↓
chunking A/B/C
        ↓
embedding model thật
        ↓
PostgreSQL + pgvector
        ↓
top-3 retrieval + trace + metrics
        ↓
OpenRouter generation trong web demo
```

### 1. Corpus và manifest

`starter/scripts/download_python_docs.py` tải 30 unit HTML từ Python 3.15.2 và
tạo `starter/data/manifest.json`. Manifest giữ URL, version, section, module và
số ký tự để truy vết nguồn.

### 2. Ingestion và chunking

`starter/src/ingestion.py` bỏ phần giao diện HTML, chuẩn hóa text và giữ
`document_id`, source và unit ID. Strategy A dùng cửa sổ 500 ký tự với overlap 50;
B dùng paragraph tối đa 800 ký tự; C dùng chunk giống B nhưng có metadata filter.

### 3. Embedding và vector store

Embedding được tạo bằng OpenRouter/OpenAI-compatible API. Vector và metadata được
lưu trong PostgreSQL + pgvector, tìm kiếm theo cosine distance.

### 4. Evaluation

`starter/src/evaluation.py` chạy cùng 20 câu hỏi cho cả A/B/C, lưu top-3 trace và
tính Hit@1/Evidence Hit@3 theo split dev/test. Coherence, metadata usefulness và
grounding phải được audit thủ công riêng.

### 5. Web demo

Chạy:

```powershell
cd starter
python web_demo.py
```

Mở `http://127.0.0.1:8000`. Giao diện hiển thị hai bên:

- Retrieval: top-3 evidence, score, source, unit và metadata.
- Generation: câu trả lời tiếng Việt từ OpenRouter dựa trên evidence.

Nếu evidence không đủ, generation trả về:

> Tài liệu hiện có không cung cấp đủ thông tin để trả lời câu hỏi này.

Luôn giữ hai phần riêng để biết hệ thống truy xuất được gì và LLM đã diễn đạt
như thế nào.
