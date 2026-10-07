# Author-review research paper

Author: Mohd Bilal ? Independent researcher; MSc Data Science, CU ?28.

Open `HalfTrend_NIFTY50_Review_Draft.docx` for editing and the PDF for a 27-page preview. The Word file embeds all 11 figures and 23 editable tables. Appendices summarize all 60 Stage 2 and 180 Stage 3 runs; supplemental CSV files preserve additional metrics. Full ledgers remain in the completed result directories identified in Appendix D.

The paper includes an abstract, literature, data audit, methods, results, costs, capital illustration, limitations, references and reproduction commands. Start labels are primary; end grouping is a robustness comparison. Futures remain an index-based proxy; every options study is SIMULATED.

## Before submission

Follow `AUTHOR_REVIEW_CHECKLIST.txt`. The exact Kaggle URL, dataset permissions, original indicator citation, correspondence email, full institution wording and author declarations require review. No confidence intervals or significance claims have been added. This is an author-review draft, not a certification of submission readiness.

## Document reproduction

From the repository root, choose a new output directory:

```powershell
python paper/build_review_draft.py --output paper/HalfTrend_NIFTY50_Review_v2
python paper/export_review_documents.py paper/HalfTrend_NIFTY50_Review_v2
```

Assembly reads completed results and regenerates presentation figures; it does not run backtests. The builder requires NumPy, pandas and Matplotlib. The exporter requires Pillow and ReportLab, plus Windows Times New Roman font files. No research dependency configuration was changed.

Word automation was unavailable in the noninteractive session (HRESULT 0x80070520). The editable Word file was generated directly as validated OOXML; the PDF was typeset independently with ReportLab. All PDF pages were rendered for layout inspection. Check Word pagination after opening it because it can differ from the preview.

`source_manifest.json`, `assembly_verification.json` and `document_export_verification.json` record provenance and checks. All original input hashes, including the raw CSV, were verified unchanged. Repository Ruff and Black checks pass. Prior results were preserved; no strategies were rerun and nothing was committed, pushed or submitted.
