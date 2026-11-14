# Báo cáo cá nhân — Lê Sỹ Long Nhật — Day 6 Data Ingestion Engineering

> MSSV: `2A202603881` · Email: `26ai.nhatlsl@vinuni.edu.vn` · GitHub: `longnhat2kruoi`

> Nên đổi tên file này thành `2A202603881_LeSyLongNhat.md` trước khi nộp.

## Dữ liệu và pipeline

Corpus là Python 3.15.2 Documentation, lấy từ trang chính thức:
`https://docs.python.org/3.15/index.html`. Corpus gồm 30 unit HTML thuộc Tutorial
và Library Reference, lưu trong `starter/data/corpus/`, với manifest tại
`starter/data/manifest.json`.

Nội dung sử dụng theo Python Software Foundation License; license và URL nguồn
được ghi trong manifest. Vì HTML không có số trang PDF, `unit_id` được dùng làm
vị trí truy vết tương đương page. Mỗi unit có URL, version, section, module và
số ký tự.

Pipeline thực hiện:

1. Đọc HTML và bỏ navigation/script/style.
2. Chuẩn hóa Unicode và whitespace.
3. Tạo fixed-size hoặc paragraph chunks.
4. Tạo embedding bằng OpenRouter, model `openai/text-embedding-3-small`.
5. Lưu vector, text và metadata trong PostgreSQL + pgvector.
6. Truy vấn top-3 và lưu trace tại `starter/results/traces.json`.

Metadata gồm `document_id`, `source`, `page`/`unit_id`, `section`, `module` và
`version`. Các trường filter lấy từ manifest, không tự tạo thêm giá trị.

## Cấu hình và benchmark

- **A:** fixed-size, kích thước 500 ký tự, overlap 50, không filter.
- **B:** theo paragraph, giới hạn 800 ký tự, không filter.
- **C:** giống B, nhưng dùng metadata filter khi câu hỏi cung cấp filter.

Ba chiến lược dùng chung corpus, embedding model, vector store và benchmark.
Benchmark có 20 câu: 15 dev, 5 test; có 3 câu metadata filter, trong đó có câu
test. Evidence của từng câu nằm trong `starter/benchmark/questions.json`.

Tiêu chí chọn chiến lược được cố định trước khi xem test: ưu tiên Evidence Hit@3,
sau đó Hit@1. Coherence, metadata và grounding được dùng để phân tích trade-off,
không suy ra chỉ từ điểm retrieval.

## Kết quả retrieval

| Strategy | Split | Hit@1 | Evidence Hit@3 | Chunk count |
|---|---:|---:|---:|---:|
| A | dev | 4/15 | 6/15 | 1956 |
| A | test | 2/5 | 2/5 | 1956 |
| B | dev | 5/15 | 11/15 | 1287 |
| B | test | 2/5 | 3/5 | 1287 |
| C | dev | 6/15 | 12/15 | 1287 |
| C | test | 3/5 | 5/5 | 1287 |

| Strategy | Hit@1 tổng | Evidence Hit@3 tổng |
|---|---:|---:|
| A | 6/20 (30%) | 8/20 (40%) |
| B | 7/20 (35%) | 14/20 (70%) |
| C | 9/20 (45%) | 17/20 (85%) |

B cải thiện Evidence Hit@3 so với A từ 40% lên 70%, cho thấy chunk theo paragraph
giữ ngữ cảnh tốt hơn fixed-size chunk. C tăng Evidence Hit@3 thêm 15 điểm phần
trăm so với B và đạt 5/5 trên test, cho thấy metadata filter giúp thu hẹp phạm vi
truy xuất khi câu hỏi có filter. Tuy nhiên Hit@1 của C chỉ đạt 9/20, nên chunk
đúng chưa luôn đứng ở vị trí đầu tiên.

## Audit thủ công

Các bảng dưới đây cần được điền sau khi chấm thủ công từ cùng trace top-3; không
dùng Hit@3 để thay thế audit.

| Strategy | Coherence trung bình /2 | Metadata đúng/đủ | Filter tuân thủ | Grounding 0/1/2 và trung bình |
|---|---|---|---|---|
| A | `<chưa chấm>` | `<chưa chấm>` | `<chưa chấm>` | `<chưa chấm>` |
| B | `<chưa chấm>` | `<chưa chấm>` | `<chưa chấm>` | `<chưa chấm>` |
| C | `<chưa chấm>` | `<chưa chấm>` | `<chưa chấm>` | `<chưa chấm>` |

Chọn trước 10 vị trí nguồn cố định để chấm coherence và 5 câu test để chấm
metadata/grounding. Người chấm là tác giả bài nên cần ghi nguy cơ thiên lệch.

## Phân tích và kết luận

Chiến lược được chọn là **C** vì đạt Evidence Hit@3 cao nhất trên cả dev và test.
Đánh đổi là C phụ thuộc vào metadata filter hợp lệ được cung cấp trước truy xuất;
với câu hỏi không có filter, C hoạt động như B. B có ít chunk hơn A và cho evidence
tốt hơn, nhưng A vẫn có thể hữu ích khi tài liệu không có cấu trúc paragraph ổn định.

Các lỗi cần kiểm tra trong trace gồm: evidence đúng nằm ở vị trí 2/3 thay vì top-1;
hoặc chunk có source/unit đúng nhưng bị cắt thiếu ngữ cảnh/evidence quote.

Giới hạn: benchmark chỉ có 20 câu, test chỉ có 5 câu, corpus chỉ gồm Python 3.15.2.
Thời gian/chi phí embedding và số chiều model cần ghi bổ sung từ log chạy thực tế.
Kết quả không đại diện cho mọi corpus.

## Tái lập

```powershell
cd starter
python -m pip install -r requirements.txt
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
python -m src.run
```

Kết quả lưu tại `starter/results/metrics.json` và `starter/results/traces.json`;
cấu hình thí nghiệm nằm trong `artifacts/experiment_log.csv`.
