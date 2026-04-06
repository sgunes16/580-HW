# LangSmith Configuration Sweep

- Dataset: `rag580-eval`
- LangSmith experiments executed: yes
- Configurations tested: 10
- Ranking score: `0.4*correctness + 0.3*groundedness + 0.2*relevance + 0.1*conciseness`

## Experiment Summary

| # | chunk_size | chunk_overlap | top_k | correctness | relevance | groundedness | conciseness | composite |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 500 | 80 | 3 | 0.2407 | 0.7926 | 0.5444 | 0.2325 | 0.4414 |
| 2 | 2000 | 240 | 5 | 0.2309 | 0.8035 | 0.5279 | 0.2100 | 0.4324 |
| 3 | 650 | 90 | 3 | 0.2337 | 0.7356 | 0.5141 | 0.2700 | 0.4218 |
| 4 | 1550 | 190 | 5 | 0.2224 | 0.7516 | 0.5268 | 0.1850 | 0.4158 |
| 5 | 1750 | 210 | 5 | 0.2175 | 0.7868 | 0.5160 | 0.1500 | 0.4142 |
| 6 | 1400 | 170 | 4 | 0.1903 | 0.8014 | 0.4837 | 0.1750 | 0.3990 |
| 7 | 800 | 100 | 4 | 0.2007 | 0.7301 | 0.5037 | 0.1975 | 0.3972 |
| 8 | 1250 | 150 | 4 | 0.1977 | 0.7617 | 0.4847 | 0.1625 | 0.3931 |
| 9 | 950 | 120 | 4 | 0.1988 | 0.7667 | 0.4616 | 0.2075 | 0.3921 |
| 10 | 1100 | 130 | 4 | 0.1923 | 0.7505 | 0.4754 | 0.1725 | 0.3869 |

## Best Configuration

- Best config: `chunk_size=500, chunk_overlap=80, top_k=3`
- Composite score: `0.4414`
- correctness: `0.2407`
- relevance: `0.7926`
- groundedness: `0.5444`
- conciseness: `0.2325`

## Difficulty Breakdown For Best Config

| Difficulty | Count | Correctness | Relevance | Groundedness | Conciseness |
|---|---:|---:|---:|---:|---:|
| easy | 8 | 0.3147 | 0.7396 | 0.6078 | 0.2250 |
| medium | 8 | 0.1869 | 0.7916 | 0.4757 | 0.1000 |
| hard | 4 | 0.2003 | 0.9008 | 0.5549 | 0.5125 |

## Justification

The selected configuration maximizes the weighted composite score while balancing answer correctness and groundedness. This weighting favors factually aligned, source-supported answers over merely question-matching outputs. Compare the easy/medium/hard rows above to verify whether the best setting wins consistently or only on one difficulty bucket.

- LangSmith experiment URL: https://smith.langchain.com/o/d19dcd8b-bb51-4719-baa8-5a04e7065237/datasets/87dc55e9-0b97-4345-9242-5f98ee3d6152/compare?selectedSessions=02cde23a-a17a-4318-89c3-80462ad761d4
