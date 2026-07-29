"""搜索质量评测 + RRF 调参(ADR-0003,PRD §8.3)。

用评测集(queries.json)计算 nDCG@10 / Recall@10,比较不同 RRF 参数。
评测集需人工扩充(30-50 查询 + 相关性标注);当前为框架 + 初始样本。

用法:
  docker compose exec api python3 - << 'PY'
  import sys; sys.path.insert(0,'/app')
  from app.eval.eval_search import run_eval
  run_eval()
  PY
"""
import json
import os
import urllib.parse
from pathlib import Path

import httpx

QUERY_FILE = Path(__file__).parent / "queries.json"
API = "http://localhost:8000"


def _login() -> str:
    c = httpx.Client(timeout=30)
    return c.post(f"{API}/api/auth/login", json={"username": "admin", "password": "changeme123"}).json()["access_token"]


def _search(token: str, query: str, k: int = 10) -> list[dict]:
    c = httpx.Client(timeout=60)
    r = c.get(f"{API}/api/search/slides?q={urllib.parse.quote(query)}&page_size={k}",
              headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        return []
    return [h["slide"] for h in r.json()]


def _dcg(rels: list[int]) -> float:
    return sum(rel / (i + 1) for i, rel in enumerate(rels))  # simplified dcg


def run_eval(k: int = 10) -> dict:
    """对评测集跑搜索,计算 Recall@K 与 nDCG@K。返回汇总。"""
    if not QUERY_FILE.exists():
        return {"error": f"评测集不存在:{QUERY_FILE}"}
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    token = _login()

    recalls = []
    ndcgs = []
    per_query = []
    for q in queries:
        results = _search(token, q["query"], k)
        result_titles = {(r.get("title") or "").strip() for r in results}
        relevant = set(q.get("relevant_titles", []))
        if not relevant:
            continue  # 无标注的跳过
        hit = result_titles & relevant
        recall = len(hit) / len(relevant) if relevant else 0
        # ndcg: 相关文档排在越前越好
        rels = [1 if (r.get("title") or "").strip() in relevant else 0 for r in results]
        idcg = _dcg(sorted(rels, reverse=True))
        ndcg = _dcg(rels) / idcg if idcg > 0 else 0
        recalls.append(recall)
        ndcgs.append(ndcg)
        per_query.append({"query": q["query"], "recall": round(recall, 2), "ndcg": round(ndcg, 3),
                          "type": q.get("type")})

    summary = {
        "queries_evaluated": len(recalls),
        "recall_at_k_mean": round(sum(recalls) / len(recalls), 3) if recalls else 0,
        "ndcg_at_k_mean": round(sum(ndcgs) / len(ndcgs), 3) if ndcgs else 0,
        "k": k,
        "per_query": per_query,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    run_eval()
