from __future__ import annotations

import argparse

from .evaluation import run_evaluation, write_evaluation


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run baseline-versus-proposed evaluation and error analysis.")
    parser.add_argument("--dataset", default="data/generated_outputs.jsonl")
    parser.add_argument("--ground-truth", default="data/ground_truth.csv")
    parser.add_argument("--mapping", default="data/import_distribution_mappings.json")
    parser.add_argument("--cache-dir", default="data/pypi_cache")
    parser.add_argument("--output", default="results/evaluation.json")
    args = parser.parse_args(argv)
    result = run_evaluation(
        args.dataset,
        args.ground_truth,
        mapping_path=args.mapping,
        cache_dir=args.cache_dir,
    )
    output_paths = write_evaluation(result, args.output)
    print("Evaluation written:")
    for name, path in output_paths.items():
        print(f"  {name}: {path}")
    for method, metrics in result["metrics"].items():
        print(
            f"{method}: precision={metrics['precision']:.3f}, "
            f"recall={metrics['recall']:.3f}, F1={metrics['f1']:.3f}, "
            f"FPR={metrics['false_positive_rate']:.3f}, "
            f"coverage={metrics['coverage']:.3f}, ambiguity={metrics['ambiguity_rate']:.3f}, "
            f"runtime={metrics['runtime_seconds']:.4f}s, "
            f"avg_runtime={metrics['average_runtime_seconds']:.6f}s/import, "
            f"n={metrics['total']}"
        )
    summary = result.get("evaluation_summary", {})
    for warning in summary.get("warnings", []):
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
