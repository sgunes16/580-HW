# Manual test results


| #   | Question (short)                 | Expected (summary)                                                                                                                                     | Model answer (summary)                                                                                                                             | Retrieved context sufficient? | Notes                                                                                               |
| --- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- | --------------------------------------------------------------------------------------------------- |
| 1   | Five stages of lifecycle         | Should list generation, storage, ingestion, transformation, serving.                                                                                   | Model listed all five stages and gave short explanations for each.                                                                                 | Yes                           | Good grounded answer; matched the expected stage list closely.                                      |
| 2   | Three Vs of big data             | Should identify volume, variety, velocity.                                                                                                             | Model answered with velocity, variety, and volume.                                                                                                 | Yes                           | Correct and concise.                                                                                |
| 3   | OLTP vs OLAP read/write patterns | OLTP should emphasize small key-based reads and low-latency transactional writes; OLAP should emphasize large aggregations and batch or stream writes. | Model contrasted OLTP and OLAP but drifted into generic read-heavy and write-heavy wording instead of the more precise access-pattern distinction. | Partial                       | Answer is directionally useful but less precise than the source material.                           |
| 4   | Hierarchical indexing in pandas  | Should define multi-level indexing and mention `stack` / `unstack` as the primary rearrangement actions.                                               | Model described hierarchical indexing loosely, then incorrectly focused on `loc[]`, `iloc[]`, and `xs[]` as the main rearrangement actions.        | No                            | Clear factual miss; retrieval likely did not anchor strongly enough on the relevant pandas section. |
| 5   | Reverse ETL purpose              | Should describe moving processed warehouse data back into operational systems or SaaS tools to drive actions.                                          | Model defined Reverse ETL as moving data back into source systems for data quality correction and restoring original format.                       | No                            | Incorrect framing; answer confuses activation use cases with a data repair loop.                    |


## Test environment

- Date: 2026-04-05
- `chunk_size` / `chunk_overlap` / `top_k`: `1000 / 150 / 4`
- Embedding model: `nomic-embed-text`
- LLM model: `llama3.2`

